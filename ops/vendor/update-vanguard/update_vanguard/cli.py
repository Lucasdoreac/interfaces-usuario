"""Safe discovery and durable planning CLI; execution stays fail-closed."""

from __future__ import annotations

import argparse
import dataclasses
import json
import uuid
from pathlib import Path
import time
import threading
from typing import Any, Callable

from .bridge import BridgeError, UpdateBridge
from .capability import LOCAL_CLI_CALLER, UpdateCapabilityService, UpdateOperation, UpdateRequest
from .inventory import json_text
from .agent import project_identity, wait_exit_code, wait_for_mission
from .ledger import (GRANTED_EFFECT_OPERATIONS, TRANSITIONS, ClaimAuthorityError, ClaimConflictError,
                     JobLimitError, Ledger)
from .manifest import ManifestError, load_manifest
from .resolve_uv import resolve_uv_project
from .docker_uv import DockerUvExecutor, ExecutorError


class OrphanReconcileSchedule:
    """When the runner next checks for an orphaned code gate (backoff on failure)."""

    def __init__(self, *, interval_s: float = 60, max_backoff_s: float = 900):
        self.interval_s, self.max_backoff_s = interval_s, max_backoff_s
        self.failures, self.next_at = 0, 0.0

    def due(self, now: float) -> bool:
        return now >= self.next_at

    def record(self, now: float, *, ok: bool) -> None:
        self.failures = 0 if ok else self.failures + 1
        wait = self.interval_s if ok else min(self.max_backoff_s, self.interval_s * 2 ** self.failures)
        self.next_at = now + wait


def _existing_ledger(root: Path) -> Ledger | None:
    path = root / ".sober" / "update-vanguard.sqlite3"
    if path.parent.is_symlink() or not path.is_file() or path.is_symlink():
        return None
    return Ledger(path)


def _emit(value: Any, as_json: bool) -> None:
    print(json_text(value) if as_json else json.dumps(value, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None, *, resolver=resolve_uv_project,
         candidate_test_executor_factory: Callable[[Path], Any] | None = None,
         deployment_executor_factory: Callable[[Path], Any] | None = None,
         state_root: Path | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sober-updates")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("inventory", "plan"):
        item = sub.add_parser(name)
        item.add_argument("--json", action="store_true")
        if name == "plan":
            item.add_argument("--resolve-python", action="store_true",
                              help="resolve stable uv candidates in disposable Git archives; reads upstream indexes")
            item.add_argument("--resolve-actions", action="store_true",
                              help="resolve workflow actions to immutable SHAs for their current stable major")
    run = sub.add_parser("run")
    run.add_argument("job_id")
    test = sub.add_parser("test", help="run declared gates against one exact lock candidate in isolated Docker")
    test.add_argument("job_id")
    validate = sub.add_parser("validate", help="run the canonical code gate against the exact clean plan HEAD")
    validate.add_argument("job_id", nargs="?")
    deploy = sub.add_parser("deploy", help="deploy one canonical SHA after its preflight gate allows it")
    deploy.add_argument("job_id")
    deploy.add_argument("--grant", help="production-effect grant ID; default: the single active covering grant")
    status = sub.add_parser("status")
    status.add_argument("job_id", nargs="?")
    export = sub.add_parser("export", help="export one durable job and its transitions as JSON")
    export.add_argument("job_id")
    cancel = sub.add_parser("cancel", help="cancel a job only when no live executor can still produce effects")
    cancel.add_argument("job_id")
    for name in ("recover", "rollback"):
        item = sub.add_parser(name)
        item.add_argument("job_id")
        if name == "rollback":
            item.add_argument("--grant", help="production-effect grant ID")
    grant = sub.add_parser("grant", help="record, revoke or list owner grants for production effects")
    grant_sub = grant.add_subparsers(dest="grant_command", required=True)
    issue = grant_sub.add_parser("issue")
    issue.add_argument("--principal", action="append", required=True,
                       help="actor ID allowed to use the grant (repeatable)")
    issue.add_argument("--operation", action="append", required=True,
                       choices=sorted(GRANTED_EFFECT_OPERATIONS))
    issue.add_argument("--environment", default="production")
    issue.add_argument("--source-sha", help="bind the grant to one exact source SHA")
    issue.add_argument("--expires-in-s", type=int)
    issue.add_argument("--basis", required=True, help="where the owner authorization is recorded")
    issue.add_argument("--issued-by", required=True)
    revoke = grant_sub.add_parser("revoke")
    revoke.add_argument("grant_id")
    revoke.add_argument("--reason", required=True)
    revoke.add_argument("--revoked-by", required=True)
    grant_sub.add_parser("list")
    review = sub.add_parser("review", help="record or check independent LLM review receipts per exact SHA")
    review_sub = review.add_subparsers(dest="review_command", required=True)
    review_record = review_sub.add_parser("record", help="append one review receipt to the canonical plan")
    review_record.add_argument("job_id")
    review_record.add_argument("--receipt", type=Path, required=True,
                               help="JSON receipt with the closed independent-review schema")
    review_verdict = review_sub.add_parser("verdict", help="exit 0 only if the exact SHA has a passing review")
    review_verdict.add_argument("candidate_sha")
    review_verdict.add_argument("--diff-sha256", help="digest of the candidate diff recomputed by the gate")
    claim = sub.add_parser("claim", help="file/branch ownership claims in the canonical ledger")
    claim_sub = claim.add_subparsers(dest="claim_command", required=True)
    acquire = claim_sub.add_parser("acquire", help="take every claim for a mission, or none (exit 1)")
    acquire.add_argument("--mission", type=int, required=True)
    acquire.add_argument("--holder", required=True)
    acquire.add_argument("--path", action="append", default=[], help="repository-relative path (repeatable)")
    acquire.add_argument("--branch", action="append", default=[])
    acquire.add_argument("--wait", action="store_true",
                         help="on conflict, register the mission to be woken by the release")
    claim_release = claim_sub.add_parser("release", help="release a mission's claims; never touches worktrees")
    claim_release.add_argument("--mission", type=int, required=True)
    claim_release.add_argument("--reason", required=True, choices=("completed", "failed", "merged", "discarded"))
    claim_release.add_argument("--by", required=True, help="who releases (recorded)")
    claim_release.add_argument("--holder", help="required for completed/failed")
    claim_release.add_argument("--pr", type=int, help="merged PR number (reason merged)")
    claim_release.add_argument("--merge-sha", help="full merge commit SHA (reason merged)")
    claim_release.add_argument("--owner-discard", action="store_true",
                               help="explicit owner discard (reason discarded)")
    claim_list = claim_sub.add_parser("list")
    claim_list.add_argument("--mission", type=int)
    claim_list.add_argument("--all", action="store_true", help="include released claims")
    claim_wait = claim_sub.add_parser("wait", help="block until the mission's terminal or woken event")
    claim_wait.add_argument("--mission", type=int, required=True)
    claim_wait.add_argument("--timeout", type=float)
    claim_wait.add_argument("--since", type=float, default=0.0)
    sub.add_parser("bridge-once", help="process one owner-MCP request on the trusted host")
    bridge_serve = sub.add_parser("bridge-serve", help="poll the owner-MCP mailbox on the trusted host")
    bridge_serve.add_argument("--poll-seconds", type=float, default=1.0)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    ledger_root = (state_root or root).resolve()
    candidate_test_executor = (candidate_test_executor_factory(root)
                               if candidate_test_executor_factory is not None else None)
    deployment_executor = (deployment_executor_factory(root)
                           if deployment_executor_factory is not None else None)
    capability = UpdateCapabilityService(root, resolver=resolver, allow_upstream_resolution=True,
                                         candidate_test_executor=candidate_test_executor,
                                         deployment_executor=deployment_executor,
                                         state_root=ledger_root)
    try:
        if args.command == "grant":
            grants = capability._ledger()
            if args.grant_command == "issue" and args.expires_in_s is not None \
                    and not 60 <= args.expires_in_s <= 400 * 86400:
                parser.error("--expires-in-s must be between 60 seconds and 400 days")
            try:
                if args.grant_command == "issue":
                    _emit(grants.record_grant(
                        grant_id=uuid.uuid4().hex, project_root=capability.project_id,
                        environment=args.environment, principals=args.principal,
                        operations=args.operation, source_sha=args.source_sha,
                        expires_at=(time.time() + args.expires_in_s) if args.expires_in_s else None,
                        basis=args.basis, issued_by=args.issued_by,
                    ), True)
                elif args.grant_command == "revoke":
                    _emit(grants.revoke_grant(args.grant_id, reason=args.reason,
                                              revoked_by=args.revoked_by), True)
                else:
                    _emit(grants.grants(capability.project_id), True)
            except (ValueError, KeyError) as exc:
                _emit({"error": f"grant {args.grant_command} refused: {exc}"}, True)
                return 2
            return 0
        if args.command == "review":
            reviews = capability._ledger()
            if args.review_command == "verdict":
                verdict = reviews.independent_review_verdict(
                    capability.project_id, args.candidate_sha, diff_sha256=args.diff_sha256,
                )
                _emit(verdict, True)
                return 0 if verdict["allowed"] else 1
            try:
                receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
                _emit({"review_recorded": reviews.record_independent_review(args.job_id, receipt)}, True)
            except (OSError, ValueError, KeyError) as exc:
                _emit({"error": f"review record refused: {exc}"}, True)
                return 2
            return 0
        if args.command == "claim":
            claims = capability._ledger()
            claim_space = project_identity(root)
            try:
                if args.claim_command == "acquire":
                    from .claim_guard import claim_scope_refusal

                    refusal = claim_scope_refusal(claims.path, claim_space, args.mission, args.holder)
                    if refusal:
                        _emit({"error": f"claim refused: {refusal}"}, True)
                        return 1
                    targets = [("path", item) for item in args.path] + [("branch", item) for item in args.branch]
                    _emit(claims.acquire_claims(project_root=claim_space, mission_id=args.mission,
                                                holder=args.holder, targets=targets, wait=args.wait), True)
                elif args.claim_command == "release":
                    _emit(claims.release_claims(
                        mission_id=args.mission, project_root=claim_space, reason=args.reason,
                        released_by=args.by, holder=args.holder, pr_number=args.pr,
                        merge_sha=args.merge_sha, owner_discard=args.owner_discard,
                    ), True)
                elif args.claim_command == "list":
                    _emit(claims.claims(project_root=claim_space, mission_id=args.mission,
                                        active_only=not args.all), True)
                else:
                    event = wait_for_mission(claims, args.mission, timeout=args.timeout, since=args.since)
                    _emit(event if event is not None else {"mission_id": args.mission, "event_type": "timeout"},
                          True)
                    return wait_exit_code(event)
            except ClaimConflictError as exc:
                _emit({"error": f"claim refused: {exc}", "conflicts": exc.conflicts}, True)
                return 1
            except (ClaimAuthorityError, ValueError) as exc:
                _emit({"error": f"claim {args.claim_command} refused: {exc}"}, True)
                return 2
            return 0
        if args.command == "bridge-once":
            bridge = UpdateBridge(root)
            with bridge.serving():
                result = bridge.run_once(capability, reconcile=False)
            _emit(result or {"state": "idle"}, True)
            return 0
        if args.command == "bridge-serve":
            if not 0.1 <= args.poll_seconds <= 60:
                parser.error("--poll-seconds must be between 0.1 and 60")
            bridge = UpdateBridge(root)
            stop = threading.Event()
            worker_errors: list[Exception] = []

            def worker() -> None:
                try:
                    while not stop.is_set():
                        result = bridge.run_once(capability, reconcile=False)
                        if result is None:
                            stop.wait(args.poll_seconds)
                        else:
                            print(json.dumps({"request_id": result["request_id"],
                                              "state": result["state"],
                                              "operation": result.get("request", {}).get("operation")},
                                             ensure_ascii=False), flush=True)
                except Exception as exc:
                    worker_errors.append(exc)
                    stop.set()

            try:
                with bridge.serving():
                    workers = [threading.Thread(target=worker, name=f"update-bridge-{i}")
                               for i in range(4)]
                    for thread in workers:
                        thread.start()
                    schedule = OrphanReconcileSchedule()
                    try:
                        while any(thread.is_alive() for thread in workers):
                            if schedule.due(time.monotonic()):
                                try:
                                    orphan = capability.reconcile_orphaned_code_gate()
                                except Exception as exc:  # keep serving; retry with backoff
                                    orphan = None
                                    schedule.record(time.monotonic(), ok=False)
                                    print(json.dumps({"orphan_reconcile": "failed",
                                                      "error": type(exc).__name__}), flush=True)
                                else:
                                    schedule.record(time.monotonic(), ok=orphan.ok)
                                    if orphan.data is not None:
                                        print(json.dumps({"orphan_reconcile": orphan.data,
                                                          "blocker": orphan.blocker},
                                                         ensure_ascii=False), flush=True)
                            for thread in workers:
                                thread.join(timeout=0.2)
                    except KeyboardInterrupt:
                        stop.set()
                        for thread in workers:
                            thread.join()
                        return 130
                    if worker_errors:
                        raise BridgeError(f"bridge worker stopped: {type(worker_errors[0]).__name__}")
            except KeyboardInterrupt:
                return 130
        if args.command == "inventory":
            result = capability.dispatch(UpdateRequest(UpdateOperation.INVENTORY), LOCAL_CLI_CALLER)
            _emit(result.data, args.json)
            return 0 if result.ok and result.data["coverage"] == "complete" else 2
        if args.command == "plan":
            result = capability.dispatch(UpdateRequest(UpdateOperation.PLAN,
                                                       resolve_python=args.resolve_python,
                                                       resolve_actions=args.resolve_actions), LOCAL_CLI_CALLER)
            _emit(result.data, args.json)
            return 0 if result.ok else 2
        if args.command == "status":
            result = capability.dispatch(UpdateRequest(UpdateOperation.STATUS, job_id=args.job_id), LOCAL_CLI_CALLER)
            _emit(result.data if result.ok else {"error": result.blocker}, True)
            return 0 if result.ok else 1
        if args.command == "validate":
            result = capability.dispatch(
                UpdateRequest(UpdateOperation.VALIDATE, job_id=args.job_id), LOCAL_CLI_CALLER
            )
            data = dict(result.data) if isinstance(result.data, dict) else {}
            if result.blocker:
                data["blocker"] = result.blocker
            _emit(data if data else {"error": result.blocker}, True)
            return 0 if result.ok else 2
        if args.command == "deploy":
            result = capability.dispatch(
                UpdateRequest(UpdateOperation.DEPLOY, job_id=args.job_id),
                dataclasses.replace(LOCAL_CLI_CALLER, grant_id=args.grant),
            )
            data = dict(result.data) if isinstance(result.data, dict) else {}
            if result.blocker:
                data["blocker"] = result.blocker
            _emit(data if data else {"error": result.blocker}, True)
            return 0 if result.ok else 2
        if args.command == "rollback":
            result = capability.dispatch(
                UpdateRequest(UpdateOperation.ROLLBACK, job_id=args.job_id),
                dataclasses.replace(LOCAL_CLI_CALLER, grant_id=args.grant),
            )
            data = dict(result.data) if isinstance(result.data, dict) else {}
            if result.blocker:
                data["blocker"] = result.blocker
            _emit(data if data else {"error": result.blocker}, True)
            return 0 if result.ok else 2
        ledger = _existing_ledger(ledger_root)
        if ledger is None:
            _emit({"error": "job not found", "job_id": args.job_id}, True)
            return 1
        job = ledger.get(args.job_id)
        if job is None:
            _emit({"error": "job not found", "job_id": args.job_id}, True)
            return 1
        if args.command == "run":
            if job["state"] == "planned":
                ledger.transition(args.job_id, "blocked", "execution disabled: updater adapters are not configured")
            _emit({"job_id": args.job_id, "state": ledger.get(args.job_id)["state"],
                   "blocker": "automatic update execution is fail-closed until stable resolvers, risk gates and executor are installed"}, True)
            return 2
        if args.command == "test":
            result = capability.dispatch(
                UpdateRequest(UpdateOperation.TEST, job_id=args.job_id), LOCAL_CLI_CALLER
            )
            data = dict(result.data) if isinstance(result.data, dict) else {}
            if result.blocker:
                data["blocker"] = result.blocker
            _emit(data if data else {"error": result.blocker}, True)
            return 0 if result.ok else 2
        if args.command == "recover":
            result = capability.dispatch(
                UpdateRequest(UpdateOperation.RECOVER, job_id=args.job_id), LOCAL_CLI_CALLER
            )
            data = dict(result.data) if isinstance(result.data, dict) else {}
            if result.blocker:
                data["blocker"] = result.blocker
            _emit(data if data else {"error": result.blocker}, True)
            return 0 if result.ok else 2
        if args.command == "export":
            _emit({"schema_version": 1, "job": job, "effects": ledger.effects(args.job_id),
                   "transitions": ledger.transitions(args.job_id)}, True)
            return 0
        if args.command == "cancel":
            result = capability.dispatch(UpdateRequest(UpdateOperation.CANCEL, job_id=args.job_id), LOCAL_CLI_CALLER)
            _emit(result.data if result.data is not None else {"error": result.blocker}, True)
            return 0 if result.ok else 2
        _emit({"job_id": args.job_id, "state": job["state"],
               "rollback": "blocked: no verified deployment digest or rollback adapter is configured"}, True)
        return 2
    except ManifestError as exc:
        print(str(exc))
        return 2
    except JobLimitError as exc:
        print(str(exc))
        return 2
    except ExecutorError as exc:
        print(str(exc))
        return 2
    except BridgeError as exc:
        print(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
