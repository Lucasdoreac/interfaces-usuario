"""Transport-neutral, owner-scoped capability surface for update-vanguard.

PARADIGMA: uma policy tipada compartilhada entre CLI e ingressos autenticados.
"""

from __future__ import annotations

import hashlib
import json
import copy
import os
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
import subprocess
import time
from typing import Any, Callable, Protocol
from urllib.parse import urlsplit

from .docker_uv import DockerUvExecutor, ExecutorError, ExecutorUncertain
from .inventory import git_worktree_status, inventory
from .process_identity import owner_gone, process_identity
from .ledger import CanonicalPlanError, EffectConflictError, GrantError, TRANSITIONS, JobLimitError, Ledger
from .manifest import ManifestError, load_manifest
from .resolve_uv import ResolutionError, resolve_uv_project
from .github_actions import GitHubActionsResolutionError, resolve_workflow_file
from .impact import assess_source_impact
from .risk import RiskEvidence, classify, evaluate_gates
from .versioning import package_delta

_CODE_GATE_OUTPUT_TAIL_CHARS = 12_000
# A code-gate claim recorded before owner identity existed is presumed orphaned
# only after twice the longest canonical gate (2 h): its process cannot still run.
_LEGACY_ORPHAN_AGE_S = 4 * 60 * 60


class UpdateOperation(StrEnum):
    INVENTORY = "updates.inventory"
    PLAN = "updates.plan"
    VALIDATE = "updates.validate"
    STATUS = "updates.status"
    CANCEL = "updates.cancel"
    RUN = "updates.run"
    TEST = "updates.test"
    DEPLOY = "updates.deploy"
    RECOVER = "updates.recover"
    ROLLBACK = "updates.rollback"


@dataclass(frozen=True, slots=True)
class UpdateCaller:
    """Trusted identity supplied by an authenticated transport boundary."""

    actor_id: str
    owner_authorized: bool
    grants: frozenset[UpdateOperation]
    trusted_host_runner: bool = False
    # Optional explicit production-effect grant; without it the ledger must
    # hold exactly one active grant covering the effect.
    grant_id: str | None = None


@dataclass(frozen=True, slots=True)
class UpdateRequest:
    operation: UpdateOperation
    job_id: str | None = None
    resolve_python: bool = False
    resolve_actions: bool = False


@dataclass(frozen=True, slots=True)
class UpdateResult:
    ok: bool
    data: Any
    blocker: str | None = None


class CandidateTestExecutor(Protocol):
    """Trusted project adapter for exact-candidate execution and reconciliation."""

    adapter_name: str

    def run_candidate(self, *, root: Path, job_id: str, job: dict[str, Any],
                      manifest: dict[str, Any], ledger: Ledger) -> dict[str, Any]: ...

    def reconcile_recorded(self, *, root: Path, job_id: str, job: dict[str, Any],
                           ledger: Ledger) -> dict[str, Any]: ...

    def cancel_recorded(self, *, job_id: str, job: dict[str, Any], ledger: Ledger) -> dict[str, Any]: ...

    def valid_test_receipt(self, execution: dict[str, Any], expected_sha: str | None,
                           plan: dict[str, Any]) -> bool: ...


class DeploymentExecutor(Protocol):
    """Trusted project adapter for one fixed production target."""

    adapter_name: str

    def assess(self, *, root: Path, job_id: str, job: dict[str, Any],
               manifest: dict[str, Any]) -> dict[str, Any]: ...

    def deploy(self, *, root: Path, job_id: str, job: dict[str, Any],
               manifest: dict[str, Any], assessment: dict[str, Any]) -> dict[str, Any]: ...

    def assess_rollback(self, *, root: Path, job_id: str, job: dict[str, Any],
                        manifest: dict[str, Any], deployed: dict[str, Any]) -> dict[str, Any]: ...

    def rollback(self, *, root: Path, job_id: str, job: dict[str, Any],
                 manifest: dict[str, Any], assessment: dict[str, Any]) -> dict[str, Any]: ...

    def reconcile_recorded(self, *, root: Path, job_id: str, job: dict[str, Any],
                           effect: dict[str, Any]) -> dict[str, Any]: ...


LOCAL_CLI_CALLER = UpdateCaller("local-cli", True, frozenset(UpdateOperation),
                               trusted_host_runner=True)


class UpdateCapabilityService:
    """Execute only explicitly granted operations against one fixed project.

    `caller` must be constructed after transport authentication. The service
    never accepts a project root from the request and never consults generic
    approvals or another domain's feature flags.
    """

    def __init__(self, root: Path, *, resolver: Callable[..., dict[str, Any]] = resolve_uv_project,
                 workflow_resolver: Callable[..., dict[str, Any]] = resolve_workflow_file,
                 allow_upstream_resolution: bool = False,
                 code_gate_runner: Callable[[list[str], Path], tuple[int, str]] | None = None,
                 candidate_test_executor: CandidateTestExecutor | None = None,
                 deployment_executor: DeploymentExecutor | None = None,
                 state_root: Path | None = None):
        self.root = root.resolve()
        self.state_root = (state_root or self.root).resolve()
        self.project_id = _project_identity(self.root)
        self.resolver = resolver
        self.workflow_resolver = workflow_resolver
        self.allow_upstream_resolution = allow_upstream_resolution
        self.code_gate_runner = code_gate_runner or _run_code_gate_command
        self.candidate_test_executor = candidate_test_executor
        self.deployment_executor = deployment_executor

    def dispatch(self, request: UpdateRequest, caller: UpdateCaller) -> UpdateResult:
        if not caller.actor_id.strip() or not caller.owner_authorized:
            return UpdateResult(False, None, "authenticated owner identity is required")
        if request.operation not in caller.grants:
            return UpdateResult(False, None, "updates capability was not granted to this caller")
        try:
            if request.operation is UpdateOperation.INVENTORY:
                return UpdateResult(True, inventory(self.root))
            if request.operation is UpdateOperation.STATUS:
                return self._status(request.job_id)
            if request.operation is UpdateOperation.CANCEL:
                return self._cancel(request.job_id)
            if request.operation is UpdateOperation.RUN:
                if not caller.trusted_host_runner:
                    return UpdateResult(False, None,
                                        "autonomous update execution is restricted to the trusted host runner")
                manifest = load_manifest(self.root)
                if manifest is None:
                    return UpdateResult(False, None, "project update manifest is missing")
                return self._run(request.job_id, manifest, caller)
            if request.operation is UpdateOperation.TEST:
                if not caller.trusted_host_runner:
                    return UpdateResult(False, None,
                                        "candidate execution is restricted to the trusted host runner")
                return self._test(request.job_id)
            if request.operation is UpdateOperation.DEPLOY:
                if not caller.trusted_host_runner:
                    return UpdateResult(False, None,
                                        "production deployment is restricted to the trusted host runner")
                manifest = load_manifest(self.root)
                if manifest is None:
                    return UpdateResult(False, None, "project update manifest is missing")
                return self._deploy(request.job_id, manifest, caller)
            if request.operation is UpdateOperation.ROLLBACK:
                if not caller.trusted_host_runner:
                    return UpdateResult(False, None,
                                        "production rollback is restricted to the trusted host runner")
                manifest = load_manifest(self.root)
                if manifest is None:
                    return UpdateResult(False, None, "project update manifest is missing")
                return self._rollback(request.job_id, manifest, caller)
            if request.operation is UpdateOperation.VALIDATE:
                if not caller.trusted_host_runner:
                    return UpdateResult(False, None, "canonical code gate is restricted to the trusted host runner")
                return self._validate(request.job_id)
            if request.operation is UpdateOperation.RECOVER:
                return self._recover(request.job_id)
            manifest = load_manifest(self.root)
            if request.operation is UpdateOperation.PLAN:
                limits = {"max_changed_packages": 1, "max_daily_jobs": 1, "max_concurrent_jobs": 1}
                if manifest is None:
                    manifest = {"policy": {"version": "missing", "limits": limits}}
                return self._plan(manifest, request.resolve_python, request.resolve_actions)
            return UpdateResult(False, None, f"{request.operation.value} executor is not configured")
        except ManifestError:
            return UpdateResult(False, None, "project update manifest is invalid")
        except CanonicalPlanError as exc:
            return UpdateResult(False, None, str(exc))
        except JobLimitError:
            return UpdateResult(False, None, "project update job limit reached")
        except (ExecutorError, OSError, subprocess.SubprocessError, ResolutionError,
                GitHubActionsResolutionError):
            return UpdateResult(False, None, "update operation failed; inspect the local runner receipt")

    def _plan(self, manifest: dict[str, Any], resolve_python: bool, resolve_actions: bool = False) -> UpdateResult:
        if (resolve_python or resolve_actions) and not self.allow_upstream_resolution:
            return UpdateResult(False, None,
                                "upstream resolution is restricted to the trusted host runner")
        snapshot = inventory(self.root)
        ledger = self._ledger()
        previous = ledger.canonical_plan(self.project_id)
        if (not resolve_python and not resolve_actions and previous is not None
                and previous.get("head_sha") == snapshot.get("head_sha")
                and snapshot.get("worktree_clean") is False):
            previous_receipt = previous.get("receipt", {})
            previous_plan = previous_receipt.get("plan", {}) if isinstance(previous_receipt, dict) else {}
            if isinstance(previous_plan, dict) and _candidate_set_sha256(previous_plan) is not None:
                # Preserve the exact candidate set and old receipts as history. A dirty tree
                # cannot inherit their decision: the current canonical plan becomes blocked
                # until a clean commit can bind validation and test execution to one SHA.
                receipt = copy.deepcopy(previous_receipt)
                plan = copy.deepcopy(previous_plan)
                prior_clean = plan.get("prior_clean_evidence")
                if not isinstance(prior_clean, dict):
                    prior_clean = {
                        "code_gate": plan.get("code_gate"),
                        "test_gate": plan.get("test_gate"),
                        "execution": receipt.get("execution"),
                    }
                plan["prior_clean_evidence"] = prior_clean
                receipt.pop("execution", None)
                receipt["inventory"] = snapshot
                receipt["policy_version"] = manifest["policy"]["version"]
                plan["worktree_state"] = {"head_sha": snapshot["head_sha"], "clean": False}
                plan["risk_evidence"] = {
                    **plan.get("risk_evidence", {}),
                    "project_imports_affected": None, "runtime_delta": None,
                    "api_delta": None, "persistent_data_affected": None,
                    "tests_complete": None, "backup_restore_verified": None,
                    "rollback_verified": None, "probes_verified": None,
                }
                plan["code_gate"] = {
                    "status": "blocked", "source_sha": snapshot["head_sha"],
                    "blocker": "working tree has changes not represented by this source SHA",
                }
                plan["source_change_gate"] = {
                    "allowed": False, "source_sha": snapshot["head_sha"],
                    "scope": "owner-authorized source editing only",
                    "blockers": ["source worktree is dirty"],
                }
                plan["test_gate"] = {
                    "status": "blocked", "source_sha": snapshot["head_sha"],
                    "blocker": "candidate execution requires a clean source checkout",
                }
                details = plan.setdefault("blocker_details", {})
                if not isinstance(details, dict):
                    details = plan["blocker_details"] = {}
                details["source"] = ["working tree is dirty; commit or revert local changes before validation"]
                details["coverage"] = []
                plan["coverage_evidence"] = _coverage_evidence(snapshot)
                _refresh_plan_gates(plan)
                receipt["plan"] = plan
                job_id = ledger.refresh_canonical_plan(
                    self.project_id, snapshot["head_sha"], receipt, "blocked",
                    max_daily_jobs=manifest["policy"]["limits"]["max_daily_jobs"],
                    max_concurrent_jobs=manifest["policy"]["limits"]["max_concurrent_jobs"],
                )
                return UpdateResult(False, {"job_id": job_id, **receipt},
                                    "canonical plan refreshed and blocked by dirty source state")
        resolutions: list[dict[str, Any]] = []
        action_resolutions: list[dict[str, Any]] = []
        if resolve_python:
            if snapshot["worktree_clean"] is not True or not snapshot["head_sha"]:
                resolutions.append({"error": "clean Git worktree and HEAD SHA are required"})
            else:
                for project in snapshot["python_projects"]:
                    if project.get("runtime_graph_state") != "covered":
                        resolutions.append({"project_manifest": project["manifest"],
                                            "error": "Python runtime lock graph is incomplete"})
                        continue
                    try:
                        result = self.resolver(self.root, project["manifest"], snapshot["head_sha"])
                        if result["files"]:
                            result = self._store_candidate(snapshot["head_sha"], result)
                        else:
                            result.pop("candidate_lock", None)
                        resolutions.append(result)
                    except (ResolutionError, OSError, subprocess.SubprocessError):
                        resolutions.append({"project_manifest": project["manifest"],
                                            "error": "stable resolver failed"})
        if resolve_actions:
            if snapshot["worktree_clean"] is not True or not snapshot["head_sha"]:
                action_resolutions.append({"error": "clean Git worktree and HEAD SHA are required"})
            else:
                workflow_root = self.root / ".github" / "workflows"
                github_root = self.root / ".github"
                if github_root.is_symlink() or workflow_root.is_symlink():
                    action_resolutions.append({"path": ".github/workflows",
                                               "error": "workflow directories must not be symlinks"})
                elif workflow_root.is_dir():
                    for workflow in sorted([*workflow_root.glob("*.yml"), *workflow_root.glob("*.yaml")]):
                        relative_path = workflow.relative_to(self.root).as_posix()
                        if (workflow.is_symlink() or not workflow.is_file()
                                or not workflow.resolve().is_relative_to(self.root)):
                            action_resolutions.append({"path": relative_path,
                                                       "error": "workflow path is not a regular in-root file"})
                            continue
                        try:
                            result = self.workflow_resolver(workflow)
                            # The resolver reports its input path; the ledger and candidate
                            # set require a project-relative path, never an absolute host path.
                            result["path"] = relative_path
                            if result["changed"]:
                                result = self._store_candidate_content(snapshot["head_sha"], result)
                            else:
                                result.pop("content", None)
                            action_resolutions.append(result)
                        except (GitHubActionsResolutionError, OSError, subprocess.SubprocessError):
                            action_resolutions.append({"path": relative_path,
                                                       "error": "stable GitHub Actions resolver failed"})
        resolved_workflows = {item.get("path") for item in action_resolutions if not item.get("error")}
        if resolved_workflows:
            for artifact in snapshot["artifacts"]:
                if artifact["kind"] == "github-actions" and artifact["path"] in resolved_workflows:
                    artifact["state"] = "covered"
                    artifact["reason"] = "stable release metadata verified and immutable candidate recorded"
            snapshot["pending"] = [item for item in snapshot["pending"]
                                   if item not in resolved_workflows]
            snapshot["coverage"] = "complete" if not snapshot["pending"] else "pending"
        plan = _plan(snapshot, resolutions, action_resolutions,
                     probe_plan_verified=_probe_plan_verified(manifest))
        plan["source_change_gate"] = _source_change_gate(manifest, snapshot)
        # Source impact is derived from a clean, exact-HEAD Git diff and stored
        # in the same canonical plan. Missing base/evidence stays UNKNOWN; it
        # never authorizes merge or deployment by itself.
        if snapshot.get("worktree_clean") is True and snapshot.get("head_sha"):
            impact = assess_source_impact(self.root, snapshot["head_sha"])
            if impact.get("source_sha") == snapshot["head_sha"]:
                plan["impact_evidence"] = impact
                impact_risk = impact.get("risk_evidence")
                if isinstance(impact_risk, dict):
                    risk_evidence = plan.get("risk_evidence")
                    if isinstance(risk_evidence, dict):
                        for key in ("project_imports_affected", "runtime_delta", "api_delta",
                                    "persistent_data_affected"):
                            value = impact_risk.get(key)
                            if value is None or type(value) is bool or isinstance(value, str):
                                risk_evidence[key] = value
                        # Candidate resolution remains authoritative when the
                        # plan actually contains candidate package changes.
                        if not plan.get("candidates"):
                            risk_evidence["package_delta"] = impact_risk.get("package_delta")
                _refresh_plan_gates(plan)
        status_required = bool(manifest.get("gates", {}).get("publish_ci_status", False))
        plan["status_publication_required"] = status_required
        if status_required:
            plan["status_publication"] = {
                "status": "pending", "source_sha": snapshot["head_sha"], "state": "success",
            }
        # Carry the owner-authored risk allowlists in the same canonical plan.
        # The plan recomputes automatic eligibility whenever evidence changes;
        # absent lists from older plan receipts continue to mean "disabled".
        plan["auto_merge_risks"] = list(manifest["policy"].get("auto_merge_risks", []))
        plan["auto_deploy_risks"] = list(manifest["policy"].get("auto_deploy_risks", []))
        policy = manifest["policy"]
        package_limit = policy["limits"]["max_changed_packages"]
        changed_count = _candidate_change_count(plan["candidates"])
        if changed_count is None:
            plan["blocker_details"]["policy"].append("candidate change count is malformed")
            _refresh_plan_blockers(plan)
        elif changed_count > package_limit:
            plan["blocker_details"]["policy"].append(
                f"candidate changes {changed_count} packages; policy limit is {package_limit}"
            )
            _refresh_plan_blockers(plan)
        _refresh_plan_gates(plan)
        receipt = {"inventory": snapshot, "plan": plan, "policy_version": policy["version"]}
        if previous is not None:
            old_plan = previous["receipt"].get("plan", {})
            old_digest = _candidate_set_sha256(old_plan)
            new_digest = _candidate_set_sha256(plan)
            same_source = previous["head_sha"] == snapshot["head_sha"]
            previous_worktree = old_plan.get("worktree_state")
            previous_was_clean = not (
                isinstance(previous_worktree, dict)
                and previous_worktree.get("clean") is False
            )
            if same_source and old_digest == new_digest and previous_was_clean:
                plan["risk_evidence"] = old_plan.get("risk_evidence", plan["risk_evidence"])
                for key in ("impact_evidence", "rollback_evidence", "deployment_evidence"):
                    if key in old_plan:
                        plan[key] = old_plan[key]
                old_test_gate = old_plan.get("test_gate")
                if old_digest is not None:
                    # Candidate-scoped tests remain valid only for an unchanged,
                    # non-empty candidate set.
                    if old_test_gate is not None:
                        plan["test_gate"] = old_test_gate
                    if "execution" in previous["receipt"]:
                        receipt["execution"] = previous["receipt"]["execution"]
                elif (isinstance(old_test_gate, dict)
                      and old_test_gate.get("scope") == "canonical-source-gate"
                      and old_test_gate.get("source_sha") == snapshot["head_sha"]):
                    # A source validation has no dependency on a candidate set
                    # when none exists; retain it across an idempotent replan.
                    plan["test_gate"] = old_test_gate
                if "code_gate" in old_plan:
                    plan["code_gate"] = old_plan["code_gate"]
                old_publication = old_plan.get("status_publication")
                if (isinstance(old_publication, dict)
                        and old_publication.get("source_sha") == snapshot["head_sha"]):
                    plan["status_publication"] = copy.deepcopy(old_publication)
                _refresh_plan_gates(plan)
            elif same_source:
                # Re-resolving dependencies/actions may change the candidate set
                # without changing the source commit. Keep source-bound receipts
                # visible in the one canonical plan, but do not let receipts for
                # the old candidate set authorize the new candidates.
                prior_source_evidence = old_plan.get("source_evidence", {})
                source_evidence = (
                    copy.deepcopy(prior_source_evidence)
                    if isinstance(prior_source_evidence, dict)
                    and prior_source_evidence.get("source_sha") == snapshot["head_sha"]
                    else {"source_sha": snapshot["head_sha"]}
                )
                old_deployment = old_plan.get("deployment_evidence")
                deployment_matches = (isinstance(old_deployment, dict)
                                      and old_deployment.get("source_sha") == snapshot["head_sha"])
                for key in ("code_gate", "impact_evidence", "deployment_evidence"):
                    evidence = old_plan.get(key)
                    if not isinstance(evidence, dict):
                        continue
                    evidence_sha = evidence.get("source_sha", evidence.get("head_sha"))
                    if evidence_sha == snapshot["head_sha"]:
                        source_evidence[key] = copy.deepcopy(evidence)
                old_rollback = old_plan.get("rollback_evidence")
                if (isinstance(old_rollback, dict)
                        and (old_rollback.get("source_sha") == snapshot["head_sha"]
                             or deployment_matches)):
                    source_evidence["rollback_evidence"] = copy.deepcopy(old_rollback)
                if len(source_evidence) > 1:
                    plan["source_evidence"] = source_evidence
                # Candidate re-resolution invalidates only candidate-bound test
                # receipts. Impact, rollback and probe facts remain usable when
                # their exact source SHA is still the planned HEAD; otherwise
                # every replan strands valid evidence in the audit trail and
                # leaves the canonical gate UNKNOWN.
                impact = source_evidence.get("impact_evidence")
                if isinstance(impact, dict) and impact.get("source_sha") == snapshot["head_sha"]:
                    risk_evidence = plan.get("risk_evidence")
                    if isinstance(risk_evidence, dict):
                        for key in ("project_imports_affected", "persistent_data_affected"):
                            value = impact.get(key)
                            if type(value) is bool:
                                risk_evidence[key] = value
                        for key, allowed in (
                            ("runtime_delta", {"none", "patch", "minor", "major"}),
                            ("api_delta", {"none", "compatible", "breaking"}),
                        ):
                            value = impact.get(key)
                            if value in allowed:
                                risk_evidence[key] = value
                        backup = impact.get("backup_restore")
                        if isinstance(backup, dict) and type(backup.get("verified")) is bool:
                            risk_evidence["backup_restore_verified"] = backup["verified"]
                rollback = source_evidence.get("rollback_evidence")
                if (deployment_matches and isinstance(rollback, dict)
                        and rollback.get("verified") is True):
                    risk_evidence = plan.get("risk_evidence")
                    if isinstance(risk_evidence, dict):
                        risk_evidence["rollback_verified"] = True
                deployment = source_evidence.get("deployment_evidence")
                if (isinstance(deployment, dict)
                        and deployment.get("source_sha") == snapshot["head_sha"]
                        and deployment.get("probes_verified") is True):
                    risk_evidence = plan.get("risk_evidence")
                    if isinstance(risk_evidence, dict):
                        risk_evidence["probes_verified"] = True
                old_code_gate = old_plan.get("code_gate")
                if (isinstance(old_code_gate, dict)
                        and old_code_gate.get("source_sha") == snapshot["head_sha"]
                        and old_code_gate.get("status") in {"passed", "failed"}):
                    plan["code_gate"] = copy.deepcopy(old_code_gate)
                # `test_gate` and `execution` bind to the candidate-set digest;
                # leave them pending for the newly resolved artifacts.
                _refresh_plan_gates(plan)
                receipt["plan"] = plan
        job_id = ledger.refresh_canonical_plan(
            self.project_id, snapshot["head_sha"], receipt,
            "blocked" if plan["blockers"] else "planned",
            max_daily_jobs=policy["limits"]["max_daily_jobs"],
            max_concurrent_jobs=policy["limits"]["max_concurrent_jobs"],
        )
        return UpdateResult(not plan["blockers"], {"job_id": job_id, **receipt},
                            "plan remains blocked by missing evidence" if plan["blockers"] else None)

    def _status(self, job_id: str | None) -> UpdateResult:
        path = self.state_root / ".sober" / "update-vanguard.sqlite3"
        if path.parent.is_symlink() or path.is_symlink() or not path.is_file():
            if job_id is None:
                return UpdateResult(True, [])
            return UpdateResult(False, None, "job not found")
        ledger = self._ledger()
        result = ledger.get(job_id) if job_id else ledger.canonical_plan(self.project_id)
        if result is None:
            return UpdateResult(True, []) if job_id is None else UpdateResult(False, None, "job not found")
        if isinstance(result, dict) and result.get("project_root") != self.project_id:
            return UpdateResult(False, None, "job not found")
        if isinstance(result, dict):
            result["effects"] = ledger.effects(job_id or result["job_id"])
            if job_id is None:
                result = [result]
        else:
            return UpdateResult(False, None, "canonical plan record is malformed")
        return UpdateResult(True, result)

    def _job_ledger(self, job_id: str | None) -> tuple[Ledger, dict[str, Any]] | UpdateResult:
        if not isinstance(job_id, str) or not re.fullmatch(r"[0-9a-f]{24}", job_id):
            return UpdateResult(False, None, "a valid job_id is required")
        path = self.state_root / ".sober" / "update-vanguard.sqlite3"
        if path.parent.is_symlink() or path.is_symlink() or not path.is_file():
            return UpdateResult(False, None, "job not found")
        ledger = self._ledger()
        job = ledger.get(job_id)
        if job is None or job["project_root"] != self.project_id:
            return UpdateResult(False, None, "job not found")
        if (ledger.canonical_plan(self.project_id) is not None
                and not ledger.is_canonical_plan(self.project_id, job["job_id"])):
            return UpdateResult(False, None, "job is historical; only the canonical plan may execute")
        return ledger, job

    def _ledger(self) -> Ledger:
        ledger = _ledger(self.state_root)
        ledger.adopt_project_identity(str(self.root), self.project_id)
        return ledger

    def _run(self, job_id: str | None, manifest: dict[str, Any], caller: UpdateCaller) -> UpdateResult:
        """Advance one canonical update through only the stages already gated.

        This is a host-runner operation, not an escape hatch: candidate tests,
        deployment preflight/effect reconciliation, and post-deploy validation
        all reuse their existing ledger-backed implementations. An uncertain
        stage is reconciled once and returned to the caller; this invocation
        never replays it.
        """
        if job_id is None:
            # A mailbox restart resubmits `updates.run` without a job id. Reuse
            # the active canonical job first: refreshing it would be rejected
            # while its executor/effect is running or uncertain and would lose
            # the only durable continuation path. _recover below reconciles it
            # before any stage can run again.
            canonical = self._ledger().canonical_plan(self.project_id)
            if (isinstance(canonical, dict)
                    and canonical.get("state") in {"running", "uncertain"}
                    and isinstance(canonical.get("job_id"), str)):
                job_id = canonical["job_id"]
            else:
                # RUN is a source-release operation. Dependency and workflow
                # resolution is an explicit PLAN operation, so a routine release
                # cannot silently turn into a large dependency-upgrade campaign.
                # Keep the unresolved inventory in the same canonical plan.
                planned = self._plan(manifest, resolve_python=False, resolve_actions=False)
                if not isinstance(planned.data, dict) or not isinstance(planned.data.get("job_id"), str):
                    return planned
                job_id = planned.data["job_id"]
        loaded = self._job_ledger(job_id)
        if isinstance(loaded, UpdateResult):
            return loaded
        ledger, job = loaded
        if not manifest.get("policy", {}).get("enabled"):
            return UpdateResult(False, {"job_id": job["job_id"], "state": job["state"]},
                                "updates capability is disabled by the project manifest")
        if job["state"] in {"running", "uncertain"}:
            recovered = self._recover(job["job_id"])
            if (not recovered.ok or not isinstance(recovered.data, dict)
                    or recovered.data.get("reconciled") is not True):
                return UpdateResult(False, recovered.data,
                                    recovered.blocker or "prior stage remains uncertain; no effect was replayed")
            loaded = self._job_ledger(job["job_id"])
            if isinstance(loaded, UpdateResult):
                return loaded
            ledger, job = loaded
            if job["state"] in {"running", "uncertain"}:
                return UpdateResult(False, {"job_id": job["job_id"], "state": job["state"]},
                                    "reconciliation did not release the active stage; no effect was replayed")

        receipt = job.get("receipt", {})
        plan = receipt.get("plan", {}) if isinstance(receipt, dict) else {}
        if not isinstance(plan, dict) or plan.get("head_sha") != job.get("head_sha"):
            return UpdateResult(False, {"job_id": job["job_id"]},
                                "canonical plan does not match its source SHA")

        candidates = plan.get("candidates", [])
        candidate_count, package_limit, candidate_blocker = _candidate_policy(
            plan, manifest.get("policy", {})
        )
        if candidate_blocker:
            return UpdateResult(False, {"job_id": job["job_id"], "state": job["state"],
                                        "plan": plan, "candidate_change_count": candidate_count,
                                        "max_changed_packages": package_limit,
                                        "effect_started": False},
                                f"{candidate_blocker}; no candidate test or deployment was started")

        # Dependency candidates need their isolated receipt before the release
        # adapter can assess promotion. No-candidate source changes use the
        # canonical full-suite gate after deployment, as the project contract
        # specifies.
        test_gate = plan.get("test_gate", {})
        if (plan.get("candidates") and
                (not isinstance(test_gate, dict) or test_gate.get("status") != "passed")):
            tested = self._test(job["job_id"])
            if not tested.ok:
                return tested
            loaded = self._job_ledger(job["job_id"])
            if isinstance(loaded, UpdateResult):
                return loaded
            ledger, job = loaded
            receipt = job["receipt"]
            plan = receipt.get("plan", {})

        deploy_key = _deploy_key(ledger, job["job_id"], job["head_sha"])
        deployed_effect = ledger.effect(job["job_id"], deploy_key)
        deploy_result = deployed_effect.get("result") if isinstance(deployed_effect, dict) else None
        deployed = (isinstance(deployed_effect, dict)
                    and deployed_effect.get("kind") == "updates.deploy"
                    and deployed_effect.get("state") == "applied"
                    and isinstance(deploy_result, dict)
                    and deploy_result.get("outcome") == "applied")
        # An applied deploy still goes through `_deploy`: its idempotent replay restores
        # the release evidence after the plan went A -> B -> A, or fails without redeploying.
        deployed_result = self._deploy(job["job_id"], manifest, caller, automatic=True)
        if deployed and not deployed_result.ok:
            return deployed_result
        if not deployed:
            # Deployment can return ok with post-deploy acceptance pending.
            # Consult the persisted effect, not the response wording, before
            # advancing to the canonical production code gate.
            loaded = self._job_ledger(job["job_id"])
            if isinstance(loaded, UpdateResult):
                return loaded
            ledger, job = loaded
            deploy_key = _deploy_key(ledger, job["job_id"], job["head_sha"])
            deployed_effect = ledger.effect(job["job_id"], deploy_key)
            deploy_result = deployed_effect.get("result") if isinstance(deployed_effect, dict) else None
            deployed = (isinstance(deployed_effect, dict)
                        and deployed_effect.get("kind") == "updates.deploy"
                        and deployed_effect.get("state") == "applied"
                        and isinstance(deploy_result, dict)
                        and deploy_result.get("outcome") == "applied")
            if not deployed:
                return deployed_result

        validated = self._validate(job["job_id"])
        loaded = self._job_ledger(job["job_id"])
        if isinstance(loaded, UpdateResult):
            return loaded
        _ledger_after, final_job = loaded
        final_plan = final_job.get("receipt", {}).get("plan", {})
        complete = _release_acceptance_passed(final_plan, final_job)
        return UpdateResult(bool(validated.ok and complete), {
            "job_id": final_job["job_id"], "state": final_job["state"],
            "plan": final_plan, "deployment": deploy_result,
            "validation": validated.data,
        }, None if complete else (validated.blocker or
                                  "canonical plan still has blockers after post-deploy validation"))

    def _test(self, job_id: str | None) -> UpdateResult:
        loaded = self._job_ledger(job_id)
        if isinstance(loaded, UpdateResult):
            return loaded
        ledger, job = loaded
        manifest = load_manifest(self.root)
        if manifest is None:
            return UpdateResult(False, None, "project update manifest is missing")
        policy = manifest.get("policy", {})
        if not policy.get("enabled"):
            return UpdateResult(False, {"job_id": job["job_id"], "state": job["state"]},
                                "updates capability is disabled by the project manifest")
        execution_adapter = manifest.get("execution", {}).get("adapter")
        executor = self._candidate_executor(execution_adapter)
        if executor is None:
            return UpdateResult(False, {"job_id": job["job_id"], "state": job["state"]},
                                "configured candidate test adapter is unavailable")
        existing_plan = job["receipt"].get("plan", {})
        existing_execution = job["receipt"].get("execution", {})
        if (isinstance(existing_plan, dict) and isinstance(existing_execution, dict)
                and existing_plan.get("test_gate", {}).get("status") == "passed"
                and existing_plan.get("risk_evidence", {}).get("tests_complete") is True
                and self._valid_execution_receipt(executor, execution_adapter,
                                                  existing_execution, job["head_sha"], existing_plan)):
            return UpdateResult(True, {"job_id": job["job_id"], "state": job["state"],
                                       "execution": existing_execution, "plan": existing_plan,
                                       "idempotent_replay": True})
        try:
            job = ledger.claim_test_execution(job["job_id"], adapter=str(execution_adapter))
        except CanonicalPlanError as exc:
            return UpdateResult(False, {"job_id": job["job_id"], "state": job["state"]}, str(exc))
        try:
            execution = executor.run_candidate(
                root=self.root, job_id=job["job_id"], job=job,
                manifest=manifest, ledger=ledger,
            )
        except ExecutorError as exc:
            saved = ledger.get(job["job_id"])
            if saved is None:
                return UpdateResult(False, {"job_id": job["job_id"]}, "job disappeared after isolated testing")
            receipt = saved["receipt"]
            execution = receipt.get("execution", {})
            if (isinstance(exc, ExecutorUncertain) or execution.get("current")
                    or execution.get("status") in {"preparing", "running"}):
                if saved["state"] == "running":
                    ledger.transition(job["job_id"], "uncertain",
                                      "isolated execution outcome requires recovery", receipt)
                saved = ledger.get(job["job_id"]) or saved
                return UpdateResult(False, {"job_id": job["job_id"], "state": saved["state"],
                                            "execution": execution},
                                    "isolated execution is uncertain; recover before refresh or retry")
            plan = receipt.get("plan")
            if isinstance(plan, dict) and isinstance(plan.get("risk_evidence"), dict):
                execution.update({"status": "failed", "source_sha": job["head_sha"]})
                plan["risk_evidence"]["tests_complete"] = False
                plan["test_gate"] = {"status": "failed", "source_sha": job["head_sha"]}
                _refresh_plan_gates(plan)
                ledger.record(job["job_id"], "isolated test setup failed; canonical plan blocked", receipt)
            if saved["state"] == "running":
                ledger.transition(job["job_id"], "blocked", "isolated test did not complete", receipt)
            saved = ledger.get(job["job_id"]) or saved
            return UpdateResult(False, {"job_id": job["job_id"], "state": saved["state"],
                                        "execution": execution, "plan": plan},
                                "isolated candidate gates did not pass")
        saved = ledger.get(job["job_id"])
        if saved is None:
            return UpdateResult(False, {"job_id": job["job_id"]}, "job disappeared after isolated testing")
        execution = saved["receipt"].get("execution", {})
        if execution.get("status") in {"passed", "failed", "cancelled"}:
            receipt = saved["receipt"]
            plan = receipt.get("plan")
            if not isinstance(plan, dict) or plan.get("head_sha") != job["head_sha"]:
                return UpdateResult(False, {"job_id": job["job_id"], "state": saved["state"]},
                                    "canonical plan is missing or does not match the job HEAD")
            passed = self._valid_execution_receipt(executor, execution_adapter,
                                                   execution, job["head_sha"], plan)
            evidence = plan.get("risk_evidence")
            if not isinstance(evidence, dict):
                return UpdateResult(False, {"job_id": job["job_id"], "state": saved["state"]},
                                    "canonical risk evidence is malformed")
            evidence["tests_complete"] = passed
            plan["test_gate"] = {
                "status": "passed" if passed else "failed",
                "source_sha": execution.get("source_sha"),
                "candidate_set_sha256": execution.get("candidate_set_sha256"),
                "commands": execution.get("declared_gate_commands", []),
                "completed_at": execution.get("completed_at"),
            }
            _refresh_plan_gates(plan)
            ledger.record(job["job_id"],
                          "isolated test evidence updated the canonical plan", receipt)
            saved = ledger.get(job["job_id"]) or saved
            if saved["state"] == "running":
                next_state = "planned" if not plan["blockers"] else "blocked"
                ledger.transition(job["job_id"], next_state,
                                  "canonical test evidence recalculated the plan gates", receipt)
                saved = ledger.get(job["job_id"]) or saved
        return UpdateResult(
            bool(plan.get("test_gate", {}).get("status") == "passed") if isinstance(
                (plan := saved["receipt"].get("plan")), dict
            ) else False,
            {"job_id": job["job_id"], "state": saved["state"], "execution": execution,
             "plan": plan},
            None if isinstance(plan, dict) and plan.get("test_gate", {}).get("status") == "passed"
            else "isolated candidate gates did not pass or did not match the canonical plan",
        )

    def _candidate_executor(self, adapter: Any) -> Any | None:
        if adapter == "docker-uv":
            return self.candidate_test_executor or DockerUvExecutor()
        custom = self.candidate_test_executor
        if custom is not None and getattr(custom, "adapter_name", None) == adapter:
            return custom
        return None

    @staticmethod
    def _valid_execution_receipt(executor: Any, adapter: Any, execution: dict[str, Any],
                                 expected_sha: str | None, plan: dict[str, Any]) -> bool:
        if execution.get("adapter") != adapter:
            return False
        if adapter == "docker-uv":
            return _valid_test_receipt(execution, expected_sha, plan)
        validator = getattr(executor, "valid_test_receipt", None)
        return bool(callable(validator) and validator(execution, expected_sha, plan))

    def _validate(self, job_id: str | None) -> UpdateResult:
        loaded = self._job_ledger(job_id)
        if isinstance(loaded, UpdateResult):
            return loaded
        ledger, job = loaded
        plan = job["receipt"].get("plan")
        if not isinstance(plan, dict) or plan.get("head_sha") != job["head_sha"]:
            return UpdateResult(False, None, "canonical plan does not match its source HEAD")
        head_sha = job["head_sha"]
        if not isinstance(head_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", head_sha):
            return UpdateResult(False, None, "canonical plan has no full source SHA")
        deploy_effect = ledger.effect(job["job_id"], _deploy_key(ledger, job["job_id"], head_sha))
        deploy_result = deploy_effect.get("result") if isinstance(deploy_effect, dict) else None
        deploy_snapshot = deploy_result.get("snapshot") if isinstance(deploy_result, dict) else None
        if (not isinstance(deploy_effect, dict) or deploy_effect.get("kind") != "updates.deploy"
                or deploy_effect.get("state") != "applied"
                or not isinstance(deploy_result, dict) or deploy_result.get("outcome") != "applied"
                or not isinstance(deploy_snapshot, dict)
                or deploy_snapshot.get("source_sha") != head_sha):
            return UpdateResult(False, {"job_id": job["job_id"], "source_sha": head_sha},
                                "canonical production code gate is available only after the exact SHA is deployed")
        git = _git_snapshot(self.root)
        if git != {"head_sha": head_sha, "clean": True}:
            return UpdateResult(False, {"job_id": job["job_id"], "git": git},
                                "canonical code gate requires the exact clean plan HEAD")
        try:
            manifest = load_manifest(self.root)
        except ManifestError as exc:
            return UpdateResult(False, {"job_id": job["job_id"]}, str(exc))
        if manifest is None:
            return UpdateResult(False, {"job_id": job["job_id"]},
                                "project update manifest is missing")

        status_required = bool(manifest.get("gates", {}).get("publish_ci_status", False))
        prior_code_gate = plan.get("code_gate", {})
        prior_publication = plan.get("status_publication", {})
        suite_passed = _canonical_suite_passed(plan, head_sha)
        publication_confirmed = _status_publication_confirmed(plan, head_sha)
        if suite_passed and (not status_required or publication_confirmed):
            return UpdateResult(True, {"job_id": job["job_id"], "state": job["state"],
                                       "plan": plan, "reused": True}, None)
        status_retry = status_required and suite_passed and not publication_confirmed

        running = dict(job["receipt"])
        running_plan = dict(plan)
        running_gate = dict(prior_code_gate) if isinstance(prior_code_gate, dict) else {}
        running_gate.update({"status": "running", "source_sha": head_sha,
                             "suite_passed": suite_passed if status_retry else False,
                             "started_at": _utc_now(), "owner": _process_identity()})
        running_plan["code_gate"] = running_gate
        running_plan["status_publication_required"] = status_required
        publication: dict[str, Any] | None = None
        if status_retry:
            running_plan["status_publication"] = {
                **(prior_publication if isinstance(prior_publication, dict) else {}),
                "status": "running", "source_sha": head_sha, "state": "success",
            }
        running["plan"] = running_plan
        try:
            ledger.claim_code_gate(job["job_id"], running)
        except (CanonicalPlanError, RuntimeError) as exc:
            return UpdateResult(False, {"job_id": job["job_id"], "state": job["state"]}, str(exc))

        role_command = ["python3", "-m", "ops.env_contract", "role"]
        ci_command = ["python3", "-m", "ops.ci", "--expect", head_sha]
        if status_retry:
            ci_command = ["python3", "-m", "ops.ci", "--publish-status", "--expect", head_sha]
        commands = [role_command, ci_command]
        results: list[dict[str, Any]] = []
        prior_results = []
        if status_retry and isinstance(prior_code_gate, dict):
            old_results = prior_code_gate.get("commands")
            if isinstance(old_results, list):
                prior_results = [item for item in old_results if isinstance(item, dict)
                                 and isinstance(item.get("command"), list)
                                 and "--publish-status" not in item["command"]]
        failure: str | None = None
        try:
            for command in commands:
                code, output = self.code_gate_runner(command, self.root)
                encoded_output = output.encode("utf-8", errors="replace")
                results.append({"command": command, "exit_code": int(code),
                                "output_bytes": len(encoded_output),
                                "output_sha256": hashlib.sha256(encoded_output).hexdigest(),
                                "output_tail": output[-_CODE_GATE_OUTPUT_TAIL_CHARS:]})
                if code != 0:
                    failure = f"canonical gate command failed with exit code {code}"
                    break
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            results.append({"error": type(exc).__name__})
            failure = "canonical gate command could not complete"
        if status_retry:
            suite_passed = True
            status_result = next((item for item in reversed(results)
                                  if item.get("command") == ci_command), {"exit_code": 2})
            status_attempt = int(prior_publication.get("attempt", 0)) + 1 \
                if isinstance(prior_publication, dict) else 1
            publication = {
                "status": "confirmed" if status_result.get("exit_code") == 0 else "failed",
                "source_sha": head_sha, "state": "success", "attempt": status_attempt,
                "command": ci_command, "exit_code": status_result.get("exit_code"),
                "output_bytes": status_result.get("output_bytes"),
                "output_sha256": status_result.get("output_sha256"),
                "output_tail": status_result.get("output_tail", ""),
                "completed_at": _utc_now(),
            }
            if publication["status"] != "confirmed":
                failure = "required GitHub commit status could not be confirmed"
        else:
            suite_passed = failure is None

        if suite_passed and status_required and not status_retry:
            # Persist the suite receipt before the remote write. If the host
            # dies during publication, recovery retries only this small effect.
            claimed = ledger.get(job["job_id"])
            claimed_plan = claimed.get("receipt", {}).get("plan") if claimed else None
            if not isinstance(claimed_plan, dict) or claimed_plan.get("head_sha") != head_sha:
                return UpdateResult(False, {"job_id": job["job_id"]},
                                    "canonical plan changed before status publication")
            claimed_plan["status_publication_required"] = True
            claimed_plan["status_publication"] = {"status": "running", "source_sha": head_sha,
                                                   "state": "success", "attempt": 1}
            claimed_plan["code_gate"] = {
                "status": "running", "source_sha": head_sha, "suite_passed": True,
                "commands": results, "started_at": _utc_now(),
            }
            evidence = claimed_plan.get("risk_evidence")
            candidates = claimed_plan.get("candidates")
            if isinstance(evidence, dict) and isinstance(candidates, list) and not candidates:
                evidence["tests_complete"] = True
                claimed_plan["test_gate"] = {"status": "passed", "source_sha": head_sha,
                                               "scope": "canonical-source-gate",
                                               "completed_at": _utc_now()}
            _refresh_plan_gates(claimed_plan)
            ledger.record(job["job_id"], "canonical source suite passed; status publication pending",
                          claimed["receipt"])

            status_command = ["python3", "-m", "ops.ci", "--publish-status", "--expect", head_sha]
            try:
                status_code, status_output = self.code_gate_runner(status_command, self.root)
                encoded_output = status_output.encode("utf-8", errors="replace")
                status_result = {"command": status_command, "exit_code": int(status_code),
                                 "output_bytes": len(encoded_output),
                                 "output_sha256": hashlib.sha256(encoded_output).hexdigest(),
                                 "output_tail": status_output[-_CODE_GATE_OUTPUT_TAIL_CHARS:]}
            except (OSError, subprocess.SubprocessError, ValueError) as exc:
                status_code = 2
                status_result = {"command": status_command, "exit_code": status_code,
                                 "error": type(exc).__name__}
            results.append(status_result)
            publication = {
                "status": "confirmed" if status_code == 0 else "failed",
                "source_sha": head_sha, "state": "success", "attempt": 1,
                "command": status_command, "exit_code": status_code,
                "output_bytes": status_result.get("output_bytes"),
                "output_sha256": status_result.get("output_sha256"),
                "output_tail": status_result.get("output_tail", ""),
                "completed_at": _utc_now(),
            }
            if status_code != 0:
                failure = "required GitHub commit status could not be confirmed"

        receipt = ledger.get(job["job_id"])
        if receipt is None:
            return UpdateResult(False, None, "canonical plan disappeared during code validation")
        updated = receipt["receipt"]
        current_plan = updated.get("plan")
        if not isinstance(current_plan, dict) or current_plan.get("head_sha") != head_sha:
            return UpdateResult(False, {"job_id": job["job_id"], "state": receipt["state"]},
                                "canonical plan changed during code validation")
        current_plan["status_publication_required"] = status_required
        current_plan["code_gate"] = {
            "status": "passed" if suite_passed else "failed", "source_sha": head_sha,
            "suite_passed": suite_passed, "commands": prior_results + results,
            "completed_at": _utc_now(),
        }
        if status_required and isinstance(publication, dict):
            current_plan["status_publication"] = publication
        evidence = current_plan.get("risk_evidence")
        candidates = current_plan.get("candidates")
        if isinstance(evidence, dict) and isinstance(candidates, list) and not candidates:
            # With no proposed dependency candidates, ops.ci is the complete
            # applicable suite for this source SHA. Candidate plans still need
            # their separate isolated execution receipt.
            evidence["tests_complete"] = suite_passed
            current_plan["test_gate"] = {
                "status": "passed" if suite_passed else "failed",
                "source_sha": head_sha,
                "scope": "canonical-source-gate",
                "completed_at": _utc_now(),
            }
        _refresh_plan_gates(current_plan)
        next_state = "planned" if not current_plan.get("blockers") else "blocked"
        saved = ledger.finish_code_gate(job["job_id"], updated, next_state)
        result = {"job_id": job["job_id"], "state": saved["state"] if saved else "uncertain",
                  "plan": current_plan}
        return UpdateResult(failure is None, result, failure or (
            "source code gate passed; candidate, risk, deployment, probes or rollback gates remain"
            if current_plan.get("blockers") else None))

    def _deploy(self, job_id: str | None, manifest: dict[str, Any], caller: UpdateCaller, *,
                automatic: bool = False) -> UpdateResult:
        loaded = self._job_ledger(job_id)
        if isinstance(loaded, UpdateResult):
            return loaded
        ledger, job = loaded
        policy = manifest.get("policy", {})
        deployment = manifest.get("deployment", {})
        if not policy.get("enabled") or not deployment.get("production_enabled"):
            return UpdateResult(False, {"job_id": job["job_id"], "state": job["state"]},
                                "production updates are disabled by the project manifest")
        adapter = self.deployment_executor
        expected_adapter = deployment.get("adapter")
        if (adapter is None or not isinstance(expected_adapter, str)
                or getattr(adapter, "adapter_name", None) != expected_adapter):
            return UpdateResult(False, {"job_id": job["job_id"], "state": job["state"]},
                                "configured production deployment adapter is unavailable")
        plan = job["receipt"].get("plan")
        head_sha = job.get("head_sha")
        if (not isinstance(plan, dict) or plan.get("head_sha") != head_sha
                or not isinstance(head_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", head_sha)):
            return UpdateResult(False, None, "canonical plan does not match a full source SHA")
        effect_key = _deploy_key(ledger, job["job_id"], head_sha)
        existing = ledger.effect(job["job_id"], effect_key)
        if existing is not None:
            result = existing.get("result") or {}
            if (existing.get("kind") == "updates.deploy" and existing.get("state") == "applied"
                    and result.get("outcome") == "applied"
                    and result.get("snapshot", {}).get("source_sha") == head_sha):
                proven, outcome = self._restore_applied_deploy_evidence(ledger, job, adapter, existing)
                replayed = {"job_id": job["job_id"], "deployment": result["snapshot"],
                            "idempotent_replay": True, "evidence_restored": outcome == "restored",
                            "evidence_outcome": outcome, "plan": proven or plan}
                superseded_by = (_superseding_deploy(ledger, job["job_id"], existing)
                                 if proven is None and outcome == "not-live" else None)
                if superseded_by is not None:
                    # A later deployment of another source replaced this one and the
                    # read-only observer confirms this SHA is not live: nothing about the
                    # old effect is uncertain, it is history. A NEW effect (next generation)
                    # goes through the full preflight -> deploy -> probes -> gate path;
                    # the old receipt is never reused as evidence.
                    generation = sum(1 for e in ledger.effects(job["job_id"])
                                     if _is_deploy_key(e["effect_key"], head_sha)) + 1
                    current = ledger.get(job["job_id"])
                    if current is not None:
                        ledger.record(job["job_id"],
                                      f"applied deployment superseded by {superseded_by}; "
                                      f"new deployment effect generation {generation}",
                                      current["receipt"])
                    loaded = self._job_ledger(job["job_id"])
                    if isinstance(loaded, UpdateResult):
                        return loaded
                    ledger, job = loaded
                    plan = job["receipt"].get("plan")
                    effect_key = f"deploy:{head_sha}:{generation}"
                    existing = None
                elif proven is None:
                    # Applied but unproven for this plan: never report success and never
                    # deploy again; the plan stays blocked on exactly what is missing.
                    # The refusal and its reason go to the ledger so the job explains itself.
                    current = ledger.get(job["job_id"])
                    if current is not None:
                        ledger.record(job["job_id"], f"applied deployment replay refused: {outcome}",
                                      current["receipt"])
                    missing = "; ".join(plan.get("blockers") or []) or "release evidence is missing"
                    return UpdateResult(False, {**replayed, "retry_performed": False},
                                        f"applied deployment evidence could not be restored ({outcome}); "
                                        f"no replay performed: {missing}")
                else:
                    return UpdateResult(True, replayed)
            elif existing.get("state") != "intent":
                return UpdateResult(False, {"job_id": job["job_id"], "effect": existing,
                                            "retry_performed": False},
                                    "deployment effect requires recovery; no replay performed")
        if job["state"] not in {"planned", "blocked"}:
            return UpdateResult(False, {"job_id": job["job_id"], "state": job["state"]},
                                "canonical plan is not available for a new deployment effect")
        candidate_count, package_limit, candidate_blocker = _candidate_policy(plan, policy)
        if candidate_blocker:
            return UpdateResult(False, {"job_id": job["job_id"], "state": job["state"],
                                        "candidate_change_count": candidate_count,
                                        "max_changed_packages": package_limit,
                                        "effect_started": False},
                                f"{candidate_blocker}; deployment assessment was not started")
        try:
            authority = self._effect_authority(ledger, manifest, caller, UpdateOperation.DEPLOY, head_sha)
        except GrantError as exc:
            return UpdateResult(False, {"job_id": job["job_id"], "state": job["state"],
                                        "effect_started": False},
                                f"production deployment is not granted: {exc}")
        git = _git_snapshot(self.root)
        if git.get("clean") is not True:
            return UpdateResult(False, {"job_id": job["job_id"], "git": git},
                                "production deployment requires a clean trusted runner checkout")
        try:
            assessment = adapter.assess(root=self.root, job_id=job["job_id"],
                                        job=job, manifest=manifest)
        except (ExecutorError, OSError, subprocess.SubprocessError, ValueError):
            return UpdateResult(False, {"job_id": job["job_id"]},
                                "production deployment assessment failed; no effect was started")
        risk_evidence = assessment.get("risk_evidence") if isinstance(assessment, dict) else None
        if (not isinstance(assessment, dict) or assessment.get("source_sha") != head_sha
                or (git.get("head_sha") != head_sha
                    and assessment.get("source_commit_verified") is not True)
                or not isinstance(risk_evidence, dict)):
            return UpdateResult(False, {"job_id": job["job_id"]},
                                "deployment assessment lacks exact-SHA risk and recovery evidence")
        try:
            evidence = RiskEvidence(**risk_evidence)
        except (KeyError, TypeError):
            return UpdateResult(False, {"job_id": job["job_id"]},
                                "deployment assessment risk evidence is malformed")
        try:
            impact_receipt = json.loads(ledger._effect_json(
                assessment.get("impact_evidence"), "impact evidence"))
            rollback_receipt = json.loads(ledger._effect_json(
                assessment.get("rollback_evidence"), "rollback evidence"))
            preflight_receipt = json.loads(ledger._effect_json(
                assessment.get("preflight_receipt"), "deployment preflight receipt"))
        except (TypeError, ValueError):
            return UpdateResult(False, {"job_id": job["job_id"]},
                                "deployment assessment contains invalid or sensitive receipt data")
        receipt = job["receipt"]
        plan = receipt.get("plan")
        plan["risk_evidence"] = evidence.to_receipt()
        plan["impact_evidence"] = impact_receipt
        plan["rollback_evidence"] = rollback_receipt
        plan["deployment_evidence"] = {
            "status": "preflight", "source_sha": head_sha,
            "probe_plan_verified": _probe_plan_verified(manifest),
            "runner_sha": git.get("head_sha"), "assessment": preflight_receipt,
        }
        _refresh_plan_gates(plan)
        ledger.record(job["job_id"], "production preflight evidence recorded", receipt)
        job = ledger.get(job["job_id"]) or job
        plan = job["receipt"]["plan"]
        deployment_gate = plan.get("deploy_gates", {})
        if not isinstance(deployment_gate, dict) or deployment_gate.get("allowed") is not True:
            return UpdateResult(False, {"job_id": job["job_id"], "state": job["state"],
                                        "plan": plan, "effect_started": False},
                                "canonical deployment gate blocks production deployment")
        if automatic and plan.get("auto_deploy") is not True:
            return UpdateResult(False, {"job_id": job["job_id"], "state": job["state"],
                                        "plan": plan, "effect_started": False},
                                "project policy does not authorize automatic deployment for this risk")
        intent = assessment.get("effect_intent")
        if not isinstance(intent, dict) or intent.get("source_sha") != head_sha:
            return UpdateResult(False, {"job_id": job["job_id"], "state": job["state"],
                                        "plan": plan},
                                "deployment adapter did not provide an exact-SHA effect intent")
        try:
            # Keep the exact, validated probe plan in the durable effect intent.
            # Recovery can then reconstruct the preflight proof after a crash
            # instead of replacing it with an incomplete reconciliation receipt.
            probe_paths = manifest.get("deployment", {}).get("probes", [])
            if not isinstance(probe_paths, list):
                probe_paths = []
            effect_intent = {**intent, "probe_paths": probe_paths}
            Ledger._effect_json(effect_intent, "deployment effect intent")
        except ValueError:
            return UpdateResult(False, {"job_id": job["job_id"], "plan": plan},
                                "deployment effect intent contains invalid or sensitive fields")
        effect_intent["authority"] = authority
        try:
            ledger.prepare_effect(job["job_id"], effect_key, "updates.deploy", effect_intent)
        except EffectConflictError:
            # A pre-dispatch intent for this SHA names other inputs or another
            # authority. Nothing was dispatched, so this is not an uncertain effect.
            return UpdateResult(False, {"job_id": job["job_id"], "effect_started": False,
                                        "retry_performed": False},
                                "a pre-dispatch deployment intent for this SHA has different inputs "
                                "or authority; nothing was dispatched")
        try:
            dispatch = ledger.begin_effect(job["job_id"], effect_key)
            if not dispatch.get("dispatch_started"):
                return UpdateResult(False, {"job_id": job["job_id"], "effect": dispatch,
                                            "retry_performed": False},
                                    "deployment effect was already claimed; recover before retry")
            if job["state"] in {"planned", "blocked"}:
                if job["state"] == "blocked":
                    ledger.transition(job["job_id"], "planned",
                                      "canonical preflight evidence permits deployment", job["receipt"])
                ledger.transition(job["job_id"], "running", "production deployment claimed")
            snapshot = adapter.deploy(root=self.root, job_id=job["job_id"], job=job,
                                      manifest=manifest, assessment=assessment)
            if (not isinstance(snapshot, dict) or snapshot.get("source_sha") != head_sha
                    or not isinstance(snapshot.get("target"), str) or not snapshot["target"]):
                raise ExecutorUncertain("deployment adapter returned no exact-target receipt")
            effect = ledger.reconcile_effect(
                job["job_id"], effect_key, outcome="applied",
                evidence={"source": expected_adapter, "observed_at": _utc_now(),
                          "snapshot": snapshot},
            )
        except Exception:
            current = ledger.effect(job["job_id"], effect_key)
            if current is not None and current.get("state") == "dispatching":
                ledger.mark_effect_uncertain(job["job_id"], effect_key,
                                             {"reason": "deployment adapter outcome requires reconciliation"})
            saved = ledger.get(job["job_id"])
            if saved is not None and saved["state"] == "running":
                ledger.transition(job["job_id"], "uncertain",
                                  "deployment outcome uncertain; recover before any retry", saved["receipt"])
            return UpdateResult(False, {"job_id": job["job_id"], "state": "uncertain",
                                        "retry_performed": False},
                                "deployment outcome is uncertain; recover before retry")
        receipt = (ledger.get(job["job_id"]) or job)["receipt"]
        plan = receipt["plan"]
        runner_sha = plan.get("deployment_evidence", {}).get("runner_sha")
        plan["deployment_evidence"] = {
            "status": "deployed", "source_sha": head_sha,
            "runner_sha": runner_sha,
            "effect_key": effect_key, "effect_receipt_sha256": effect["result"]["evidence_sha256"],
            "probe_plan_verified": _probe_plan_verified(manifest),
            "probes_verified": snapshot.get("probes_verified"),
            "snapshot": snapshot,
        }
        plan["risk_evidence"]["probes_verified"] = snapshot.get("probes_verified")
        _refresh_plan_gates(plan)
        saved = ledger.get(job["job_id"])
        if saved is not None and saved["state"] == "running":
            ledger.transition(job["job_id"], "blocked",
                              "deployment applied; post-deploy acceptance is pending", receipt)
        else:
            ledger.record(job["job_id"], "deployment receipt and post-deploy gate recorded", receipt)
        return UpdateResult(True, {"job_id": job["job_id"], "state": "blocked",
                                   "deployment": snapshot, "plan": plan,
                                   "effect_receipt_sha256": effect["result"]["evidence_sha256"]},
                            "deployment succeeded; canonical post-deploy tests or probes remain")

    def _restore_applied_deploy_evidence(self, ledger: Ledger, job: dict[str, Any], adapter: Any,
                                         effect: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        """Bring back an applied deploy's evidence after the plan went to another SHA and back.

        One canonical plan serves every SHA of a project, so a refresh to B and back to
        A drops A's preflight evidence while `deploy:A` stays applied, and the replay above
        skips the preflight that would recompute it: the plan then blocks forever on
        "rollback strategy is not verified". The evidence is restored only from the
        preflight receipt this job recorded for exactly this SHA, with rollback verified,
        and only after the adapter's read-only `observe_live` confirms the SHA is live, its
        probes pass and the recorded rollback target still exists. `reconcile_recorded` is
        not used here: it may restart the service, an effect this path has no grant for.
        An adapter without `observe_live` gets nothing restored (fail closed). The write is
        refused if the plan changed while the observation ran. Returns `(plan, outcome)`:
        the plan whose release evidence is proven, with outcome "already-proven" or
        "restored", or None with the stable reason the evidence could not be restored, so
        the replay fails and the ledger records why.
        """
        receipt = job.get("receipt") or {}
        plan = receipt.get("plan")
        head_sha = job.get("head_sha")
        if not isinstance(plan, dict):
            return None, "no-plan"
        risk = plan.get("risk_evidence") if isinstance(plan.get("risk_evidence"), dict) else {}
        deployed = plan.get("deployment_evidence")
        if (risk.get("rollback_verified") is True and isinstance(deployed, dict)
                and deployed.get("source_sha") == head_sha):
            return plan, "already-proven"
        preflight = None
        for transition in reversed(ledger.transitions(job["job_id"])):
            if transition.get("reason") != "production preflight evidence recorded":
                continue
            try:
                recorded = json.loads(transition.get("receipt_json") or "{}").get("plan") or {}
            except ValueError:
                continue
            if (recorded.get("head_sha") == head_sha
                    and (recorded.get("rollback_evidence") or {}).get("verified") is True
                    and (recorded.get("risk_evidence") or {}).get("rollback_verified") is True):
                preflight = recorded
                break
        if preflight is None:
            return None, "no-preflight-receipt"
        if not callable(getattr(adapter, "observe_live", None)):
            return None, "no-read-only-observer"
        version = job.get("version")
        try:
            snapshot = adapter.observe_live(root=self.root, job_id=job["job_id"], job=job,
                                            effect=effect)
            evidence = RiskEvidence(**preflight["risk_evidence"])
        except (ExecutorError, ExecutorUncertain, OSError, subprocess.SubprocessError,
                KeyError, TypeError, ValueError):
            return None, "observation-failed"
        if not isinstance(snapshot, dict) or snapshot.get("source_sha") != head_sha:
            return None, "not-live"
        if snapshot.get("probes_verified") is not True:
            return None, "probes-unverified"
        if snapshot.get("rollback_target_available") is not True:
            return None, "rollback-target-unavailable"
        current = ledger.get(job["job_id"])
        if (current is None or current.get("head_sha") != head_sha
                or current.get("version") != version):
            return None, "plan-moved"  # the plan moved while observing; never write a stale plan over it
        plan["risk_evidence"] = {**evidence.to_receipt(), "probes_verified": True}
        for key in ("impact_evidence", "rollback_evidence"):
            if isinstance(preflight.get(key), dict):
                plan[key] = copy.deepcopy(preflight[key])
        plan["deployment_evidence"] = {
            "status": "deployed", "source_sha": head_sha,
            "effect_key": effect.get("effect_key"),
            "effect_receipt_sha256": (effect.get("result") or {}).get("evidence_sha256"),
            "probes_verified": True, "snapshot": snapshot,
            "restored_from": "recorded preflight receipt and read-only live observation",
        }
        _refresh_plan_gates(plan)
        ledger.record(job["job_id"], "applied deployment evidence restored after replan", receipt)
        return plan, "restored"

    def reconcile_orphaned_code_gate(self, *, now: float | None = None) -> UpdateResult:
        """Mark the canonical code gate interrupted when its owner provably died.

        Never replays the gate and never touches an external effect: a plan
        with a dispatching or uncertain effect still needs explicit recovery.
        `data` is None when there is nothing to reconcile.
        """
        path = self.state_root / ".sober" / "update-vanguard.sqlite3"
        if path.parent.is_symlink() or path.is_symlink() or not path.is_file():
            return UpdateResult(True, None)
        ledger = self._ledger()
        job = ledger.canonical_plan(self.project_id)
        plan = job.get("receipt", {}).get("plan") if isinstance(job, dict) else None
        gate = plan.get("code_gate") if isinstance(plan, dict) else None
        if (not isinstance(gate, dict) or job.get("state") != "running"
                or gate.get("status") != "running"):
            return UpdateResult(True, None)
        evidence = _orphan_evidence(gate, time.time() if now is None else now)
        if evidence is None:
            return UpdateResult(True, None)
        if any(item.get("state") in {"dispatching", "uncertain"} for item in ledger.effects(job["job_id"])):
            return UpdateResult(False, {"job_id": job["job_id"], "orphan_evidence": evidence},
                                "orphaned code gate has an unresolved effect; explicit recovery required")
        gate.update({"status": "interrupted", "recovered_at": _utc_now(),
                     "retry_performed": False, "orphan_evidence": evidence})
        try:
            saved = ledger.finish_code_gate(
                job["job_id"], job["receipt"], "blocked",
                reason=f"orphaned code gate reconciled by host runner ({evidence['reason']}); not replayed",
                expected_version=job["version"],
            )
        except RuntimeError:
            return UpdateResult(False, {"job_id": job["job_id"]},
                                "canonical plan changed during orphan reconciliation; retry later")
        return UpdateResult(True, {"job_id": job["job_id"], "state": saved["state"],
                                   "orphan_evidence": evidence, "retry_performed": False})

    def _recover(self, job_id: str | None) -> UpdateResult:
        loaded = self._job_ledger(job_id)
        if isinstance(loaded, UpdateResult):
            return loaded
        ledger, job = loaded
        plan = job["receipt"].get("plan", {})
        code_gate = plan.get("code_gate", {}) if isinstance(plan, dict) else {}
        if (job["state"] in {"running", "uncertain"}
                and isinstance(code_gate, dict) and code_gate.get("status") == "running"):
            code_gate["status"] = "interrupted"
            code_gate["recovered_at"] = _utc_now()
            code_gate["retry_performed"] = False
            saved = ledger.finish_code_gate(
                job["job_id"], job["receipt"], "blocked",
                reason="host runner interruption reconciled; code gate was not replayed",
            )
            return UpdateResult(True, {"job_id": job["job_id"], "state": saved["state"],
                                       "plan": saved["receipt"].get("plan"),
                                       "retry_performed": False, "reconciled": True})
        execution = job["receipt"].get("execution", {})
        effects = ledger.effects(job["job_id"])
        pending_deploy_effects = [
            item for item in effects
            if item.get("kind") in {"updates.deploy", "updates.rollback"}
            and item.get("state") in {"dispatching", "uncertain"}
        ]
        if pending_deploy_effects:
            adapter = self.deployment_executor
            if adapter is None or not callable(getattr(adapter, "reconcile_recorded", None)):
                return UpdateResult(False, {"job_id": job["job_id"], "effects": effects,
                                            "retry_performed": False},
                                    "deployment reconciliation adapter is unavailable; no replay performed")
            outcomes = []
            for effect in pending_deploy_effects:
                try:
                    observation = adapter.reconcile_recorded(
                        root=self.root, job_id=job["job_id"], job=job, effect=effect,
                    )
                except Exception:
                    return UpdateResult(False, {"job_id": job["job_id"],
                                                "retry_performed": False},
                                        "deployment reconciliation failed; no replay performed")
                if not isinstance(observation, dict) or observation.get("reconciled") is not True:
                    return UpdateResult(False, {"job_id": job["job_id"], "effects": effects,
                                                "observed": observation, "retry_performed": False},
                                        "deployment effect remains uncertain; no replay performed")
                outcome = observation.get("outcome")
                if outcome not in {"applied", "not_applied"}:
                    return UpdateResult(False, {"job_id": job["job_id"], "observed": observation,
                                                "retry_performed": False},
                                        "deployment reconciliation returned an invalid outcome")
                reconciled = ledger.reconcile_effect(
                    job["job_id"], effect["effect_key"], outcome=outcome,
                    evidence={"source": "sober-compose-api", "observed_at": _utc_now(),
                              "snapshot": observation.get("snapshot", {})},
                )
                if outcome == "applied":
                    saved = ledger.get(job["job_id"]) or job
                    saved_plan = saved["receipt"].get("plan", {})
                    snapshot = observation.get("snapshot", {})
                    if isinstance(saved_plan, dict) and isinstance(snapshot, dict):
                        if effect.get("kind") == "updates.deploy":
                            intent = effect.get("intent", {})
                            probe_paths = intent.get("probe_paths") if isinstance(intent, dict) else None
                            probe_plan_verified = (
                                intent.get("source_sha") == job.get("head_sha")
                                and saved_plan.get("head_sha") == job.get("head_sha")
                                and snapshot.get("source_sha") == job.get("head_sha")
                                and _is_deploy_key(effect.get("effect_key"), job.get("head_sha"))
                                and _probe_plan_verified({"deployment": {"probes": probe_paths}})
                            )
                            saved_plan["deployment_evidence"] = {
                                "status": "deployed", "source_sha": snapshot.get("source_sha"),
                                "snapshot": snapshot, "reconciled": True,
                                "probe_plan_verified": probe_plan_verified,
                            }
                            saved_plan.setdefault("risk_evidence", {})[
                                "probes_verified"] = snapshot.get("probes_verified")
                        else:
                            saved_plan["deployment_evidence"] = {
                                "status": "rolled_back", "source_sha": snapshot.get("source_sha"),
                                "snapshot": snapshot, "reconciled": True,
                            }
                            saved_plan["rollback_evidence"] = {
                                "status": "verified", "snapshot": snapshot, "reconciled": True,
                            }
                        _refresh_plan_gates(saved_plan)
                        ledger.record(job["job_id"],
                                      "production effect receipt recovered from live state",
                                      saved["receipt"])
                outcomes.append({"effect_key": effect["effect_key"], "outcome": outcome,
                                 "effect": reconciled})
            saved = ledger.get(job["job_id"]) or job
            if saved["state"] in {"running", "uncertain"}:
                ledger.transition(job["job_id"], "blocked",
                                  "deployment effect reconciled from live production state; no replay performed",
                                  saved["receipt"])
                saved = ledger.get(job["job_id"]) or saved
            return UpdateResult(True, {"job_id": job["job_id"], "state": saved["state"],
                                       "effects": outcomes, "reconciled": True,
                                       "retry_performed": False, "plan": saved["receipt"].get("plan")})
        if (execution.get("current") or execution.get("phases")
                or execution.get("status") in {"preparing", "running"}):
            executor = self._candidate_executor(execution.get("adapter"))
            if executor is None:
                return UpdateResult(False, {"job_id": job["job_id"], "state": job["state"],
                                            "retry_performed": False},
                                    "recorded candidate executor is unavailable; no retry performed")
            result = executor.reconcile_recorded(
                root=self.root, job_id=job["job_id"], job=job, ledger=ledger,
            )
            saved = ledger.get(job["job_id"])
            if result.get("reconciled") and saved is not None:
                execution = saved["receipt"].get("execution", {})
                if execution.get("status") in {"preparing", "running"} and not execution.get("current"):
                    execution["status"] = "interrupted"
                    ledger.record(job["job_id"], "reconciled test is safe to resume", saved["receipt"])
                    saved = ledger.get(job["job_id"]) or saved
                if saved["state"] in {"running", "uncertain"}:
                    ledger.transition(job["job_id"], "blocked",
                                      "execution reconciled; canonical plan may be refreshed or resumed",
                                      saved["receipt"])
                    saved = ledger.get(job["job_id"]) or saved
            result.update({"job_id": job["job_id"], "state": (saved or job)["state"]})
            return UpdateResult(bool(result.get("reconciled")), result,
                                None if result.get("reconciled") else "recorded Docker phase remains uncertain")
        effects = ledger.effects(job["job_id"])
        unresolved = [item for item in effects if item["state"] in {"dispatching", "uncertain"}]
        if unresolved:
            return UpdateResult(False, {"job_id": job["job_id"], "state": job["state"],
                                        "effects": effects, "retry_performed": False},
                                "external effect reconciliation adapter unavailable; no retry performed")
        if job["state"] == "running":
            return UpdateResult(False, {"job_id": job["job_id"], "state": job["state"],
                                        "effects": effects, "retry_performed": False},
                                "executor liveness or effect outcome is unresolved; no state change or retry performed")
        if job["state"] == "uncertain":
            ledger.transition(job["job_id"], "blocked",
                              "no remote reconciliation adapter is configured; no retry performed")
            saved = ledger.get(job["job_id"])
            return UpdateResult(False, {"job_id": job["job_id"], "state": (saved or job)["state"],
                                        "effects": effects, "retry_performed": False},
                                "remote reconciliation adapter unavailable; job remains blocked")
        return UpdateResult(True, {"job_id": job["job_id"], "state": job["state"],
                                   "effects": effects, "reconciled": False,
                                   "retry_performed": False, "recovery_needed": False})

    def _effect_authority(self, ledger: Ledger, manifest: dict[str, Any], caller: UpdateCaller,
                          operation: UpdateOperation, source_sha: str) -> dict[str, Any]:
        """Bind one production effect to the grant that authorizes it."""
        environment = manifest.get("deployment", {}).get("environment", "production")
        if not isinstance(environment, str):
            raise GrantError("deployment environment is invalid")
        return ledger.authorize_effect(
            project_root=self.project_id, environment=environment, operation=operation.value,
            actor_id=caller.actor_id, source_sha=source_sha, grant_id=caller.grant_id,
        )

    def _rollback(self, job_id: str | None, manifest: dict[str, Any], caller: UpdateCaller) -> UpdateResult:
        loaded = self._job_ledger(job_id)
        if isinstance(loaded, UpdateResult):
            return loaded
        ledger, job = loaded
        adapter = self.deployment_executor
        expected_adapter = manifest.get("deployment", {}).get("adapter")
        if (adapter is None or not isinstance(expected_adapter, str)
                or getattr(adapter, "adapter_name", None) != expected_adapter):
            return UpdateResult(False, {"job_id": job["job_id"]},
                                "configured production rollback adapter is unavailable")
        head_sha = job.get("head_sha")
        if not isinstance(head_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", head_sha):
            return UpdateResult(False, None, "canonical plan has no full source SHA")
        deploy_key = _deploy_key(ledger, job["job_id"], head_sha)
        deployed_effect = ledger.effect(job["job_id"], deploy_key)
        deployed_result = deployed_effect.get("result") if isinstance(deployed_effect, dict) else None
        deployed = deployed_result.get("snapshot") if isinstance(deployed_result, dict) else None
        if (not isinstance(deployed_effect, dict) or deployed_effect.get("kind") != "updates.deploy"
                or deployed_effect.get("state") != "applied"
                or not isinstance(deployed, dict) or deployed.get("source_sha") != head_sha):
            return UpdateResult(False, {"job_id": job["job_id"]},
                                "rollback requires an applied deployment receipt for this exact SHA")
        restore_sha = deployed.get("previous_source_sha")
        # Provider-native immutable builds (e.g. static-site deploy IDs) are not
        # Docker images. Opt-in is explicit; old manifests retain digest checks.
        native_build = manifest.get("deployment", {}).get("artifact_kind") == "provider-build"
        previous_key = "previous_artifact_id" if native_build else "previous_image_id"
        intent_key = "restore_artifact_id" if native_build else "restore_image_id"
        restored_key = "restored_artifact_id" if native_build else "restored_image_id"
        restore_artifact = deployed.get(previous_key)
        artifact_pattern = r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}" if native_build else r"sha256:[0-9a-f]{64}"
        target = deployed.get("target")
        if (not isinstance(restore_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", restore_sha)
                or not isinstance(restore_artifact, str) or not re.fullmatch(artifact_pattern, restore_artifact)
                or not isinstance(target, str) or not target):
            return UpdateResult(False, {"job_id": job["job_id"], "deployment": deployed},
                                "deployment receipt lacks an exact source, recovery artifact and target for rollback")
        effect_key = f"rollback:{head_sha}"
        existing = ledger.effect(job["job_id"], effect_key)
        if existing is not None:
            result = existing.get("result") or {}
            snapshot = result.get("snapshot") if isinstance(result, dict) else None
            if (existing.get("kind") == "updates.rollback" and existing.get("state") == "applied"
                    and isinstance(snapshot, dict) and snapshot.get("restored_source_sha") == restore_sha
                    and snapshot.get(restored_key) == restore_artifact):
                # The applied effect alone proves nothing for this plan: after A -> B -> A
                # the plan no longer records the rollback. Never roll back again; fail and
                # record why, so the job explains itself.
                plan = job["receipt"].get("plan") or {}
                recorded = (plan.get("rollback_evidence") or {}).get("snapshot") or {}
                if ((plan.get("deployment_evidence") or {}).get("status") != "rolled_back"
                        or (plan.get("deployment_evidence") or {}).get("source_sha") != head_sha
                        or recorded.get("restored_source_sha") != restore_sha
                        or recorded.get(restored_key) != restore_artifact):
                    ledger.record(job["job_id"],
                                  "applied rollback replay refused: rollback-evidence-not-in-plan",
                                  job["receipt"])
                    return UpdateResult(False, {"job_id": job["job_id"], "rollback": snapshot,
                                                "idempotent_replay": True, "retry_performed": False},
                                        "applied rollback evidence is not recorded in the current plan; "
                                        "no replay performed")
                return UpdateResult(True, {"job_id": job["job_id"], "rollback": snapshot,
                                           "idempotent_replay": True})
            if existing.get("state") != "intent":
                return UpdateResult(False, {"job_id": job["job_id"], "effect": existing,
                                            "retry_performed": False},
                                    "rollback effect requires recovery; no replay performed")
        try:
            authority = self._effect_authority(ledger, manifest, caller, UpdateOperation.ROLLBACK, head_sha)
        except GrantError as exc:
            return UpdateResult(False, {"job_id": job["job_id"], "effect_started": False},
                                f"production rollback is not granted: {exc}")
        try:
            assessment = adapter.assess_rollback(root=self.root, job_id=job["job_id"],
                                                 job=job, manifest=manifest, deployed=deployed)
            if (not isinstance(assessment, dict) or assessment.get("source_sha") != head_sha
                    or assessment.get("restore_source_sha") != restore_sha
                    or assessment.get(intent_key) != restore_artifact
                    or assessment.get("target") != target
                    or assessment.get("rollback_verified") is not True):
                return UpdateResult(False, {"job_id": job["job_id"]},
                                    "rollback assessment does not verify the recorded recovery target")
            intent = assessment.get("effect_intent")
            if (not isinstance(intent, dict) or intent.get("source_sha") != head_sha
                    or intent.get("restore_source_sha") != restore_sha
                    or intent.get(intent_key) != restore_artifact
                    or intent.get("target") != target):
                return UpdateResult(False, {"job_id": job["job_id"]},
                                    "rollback adapter did not provide an exact recovery intent")
            Ledger._effect_json(intent, "rollback effect intent")
            try:
                preflight = json.loads(ledger._effect_json(
                    assessment.get("preflight_receipt"), "rollback preflight receipt"))
            except (TypeError, ValueError):
                return UpdateResult(False, {"job_id": job["job_id"]},
                                    "rollback assessment contains invalid or sensitive receipt data")
            intent = {**intent, "authority": authority}
            ledger.prepare_effect(job["job_id"], effect_key, "updates.rollback", intent)
            dispatch = ledger.begin_effect(job["job_id"], effect_key)
            if not dispatch.get("dispatch_started"):
                return UpdateResult(False, {"job_id": job["job_id"], "effect": dispatch,
                                            "retry_performed": False},
                                    "rollback was already claimed; recover before retry")
            if job["state"] == "blocked":
                ledger.transition(job["job_id"], "planned", "owner requested verified rollback", job["receipt"])
                ledger.transition(job["job_id"], "running", "production rollback claimed")
            elif job["state"] in {"planned", "failed"}:
                ledger.transition(job["job_id"], "running", "production rollback claimed")
            snapshot = adapter.rollback(root=self.root, job_id=job["job_id"], job=job,
                                        manifest=manifest, assessment=assessment)
            if (not isinstance(snapshot, dict) or snapshot.get("source_sha") != head_sha
                    or snapshot.get("restored_source_sha") != restore_sha
                    or snapshot.get(restored_key) != restore_artifact
                    or snapshot.get("target") != target
                    or snapshot.get("rollback_verified") is not True):
                raise ExecutorUncertain("rollback adapter returned no exact recovery receipt")
            effect = ledger.reconcile_effect(
                job["job_id"], effect_key, outcome="applied",
                evidence={"source": expected_adapter, "observed_at": _utc_now(),
                          "snapshot": snapshot},
            )
        except Exception:
            current = ledger.effect(job["job_id"], effect_key)
            if current is not None and current.get("state") == "dispatching":
                ledger.mark_effect_uncertain(job["job_id"], effect_key,
                                             {"reason": "rollback outcome requires reconciliation"})
            saved = ledger.get(job["job_id"])
            if saved is not None and saved["state"] == "running":
                ledger.transition(job["job_id"], "uncertain",
                                  "rollback outcome uncertain; recover before any retry", saved["receipt"])
            return UpdateResult(False, {"job_id": job["job_id"], "state": "uncertain",
                                        "retry_performed": False},
                                "rollback outcome is uncertain; recover before retry")
        saved = ledger.get(job["job_id"]) or job
        receipt = saved["receipt"]
        plan = receipt.get("plan", {})
        plan["rollback_evidence"] = {"status": "verified", "preflight": preflight,
                                     "snapshot": snapshot,
                                     "effect_receipt_sha256": effect["result"]["evidence_sha256"]}
        plan["risk_evidence"]["rollback_verified"] = True
        plan["deployment_evidence"] = {"status": "rolled_back", "source_sha": head_sha,
                                        "snapshot": deployed}
        ledger.transition(job["job_id"], "rolled_back", "production source and recovery artifact restored", receipt)
        return UpdateResult(True, {"job_id": job["job_id"], "state": "rolled_back",
                                   "rollback": snapshot, "plan": plan},
                            "deployment rolled back and recovery receipt recorded")

    def _cancel(self, job_id: str | None) -> UpdateResult:
        if not job_id:
            return UpdateResult(False, None, "job_id is required")
        path = self.state_root / ".sober" / "update-vanguard.sqlite3"
        if path.parent.is_symlink() or path.is_symlink() or not path.is_file():
            return UpdateResult(False, None, "job not found")
        ledger = self._ledger()
        job = ledger.get(job_id)
        if job is None or job.get("project_root") != self.project_id:
            return UpdateResult(False, None, "job not found")
        canonical = ledger.canonical_plan(self.project_id)
        if canonical is not None and not ledger.is_canonical_plan(self.project_id, job_id):
            # A superseded plan may be closed, never executed: only before any
            # effect or executor, so nothing it started can be orphaned.
            if job["state"] == "cancelled":
                return UpdateResult(True, {"job_id": job_id, "state": "cancelled", "idempotent_replay": True})
            if (job["state"] not in {"planned", "blocked"} or ledger.effects(job_id)
                    or job["receipt"].get("execution", {}).get("current")):
                return UpdateResult(False, {"job_id": job_id, "state": job["state"], "cancelled": False},
                                    "historical job has effects or an executor; reconcile before closing")
            ledger.transition(job_id, "cancelled",
                              f"historical plan superseded by canonical plan {canonical['job_id']}; "
                              "closed without execution")
            return UpdateResult(True, {"job_id": job_id, "state": "cancelled",
                                       "superseded_by": canonical["job_id"]})
        if job["state"] == "cancelled":
            return UpdateResult(True, {"job_id": job_id, "state": "cancelled", "idempotent_replay": True})
        execution = job["receipt"].get("execution", {})
        if execution.get("current"):
            executor = self._candidate_executor(execution.get("adapter"))
            if executor is None:
                return UpdateResult(False, {"job_id": job_id, "state": job["state"], "cancelled": False},
                                    "recorded candidate executor is unavailable; no cancellation performed")
            result = executor.cancel_recorded(job_id=job_id, job=job, ledger=ledger)
            result["cancelled"] = result.get("status") == "cancelled"
            if result["cancelled"] and job["state"] == "running":
                ledger.transition(job_id, "cancelled", "owner cancelled and candidate process was fenced",
                                  job["receipt"])
            return UpdateResult(result["cancelled"], result,
                                None if result.get("status") == "cancelled" else "recorded executor could not be safely cancelled")
        if job["state"] in {"running", "uncertain"}:
            return UpdateResult(False, {"job_id": job_id, "state": job["state"], "cancelled": False},
                                "executor liveness or effect outcome is unresolved; no cancellation performed")
        if any(effect["state"] in {"dispatching", "uncertain"} for effect in ledger.effects(job_id)):
            return UpdateResult(False, {"job_id": job_id, "state": job["state"], "cancelled": False},
                                "active or uncertain executor must be reconciled; no cancellation performed")
        if "cancelled" not in TRANSITIONS.get(job["state"], set()):
            return UpdateResult(False, {"job_id": job_id, "state": job["state"], "cancelled": False},
                                "job is not cancellable in its current state")
        ledger.transition(job_id, "cancelled", "owner self-chat cancelled before an external effect")
        return UpdateResult(True, {"job_id": job_id, "state": "cancelled"})

    def _store_candidate(self, head_sha: str, result: dict[str, Any]) -> dict[str, Any]:
        relative = PurePosixPath(str(result["files"][0]))
        if not relative.parts or relative.is_absolute() or ".." in relative.parts:
            raise ResolutionError("candidate lock path escapes the project")
        sober_dir = self.root / ".sober"
        candidates_dir = sober_dir / "update-vanguard-candidates"
        if sober_dir.is_symlink() or candidates_dir.is_symlink():
            raise ResolutionError("candidate storage path must not follow symlinks")
        candidate_id = hashlib.sha256(
            f"{head_sha}:{result['project_manifest']}:{result['new_lock_sha256']}".encode()
        ).hexdigest()[:24]
        relative_parent = Path(*relative.parts).parent
        directory = candidates_dir / candidate_id / relative_parent
        cursor = candidates_dir
        for part in (candidate_id, *relative_parent.parts):
            cursor = cursor / part
            if cursor.is_symlink():
                raise ResolutionError("candidate storage path must not traverse symlinks")
        if not directory.resolve().is_relative_to(candidates_dir.resolve()):
            raise ResolutionError("candidate storage path escapes managed state")
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / relative.name
        content = str(result.pop("candidate_lock"))
        if target.exists():
            if target.is_symlink() or target.read_text(encoding="utf-8") != content:
                raise ResolutionError("existing candidate artifact differs; preserving it")
        else:
            descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        result["candidate_id"] = candidate_id
        result["candidate_path"] = target.relative_to(self.root).as_posix()
        return result

    def _store_candidate_content(self, head_sha: str, result: dict[str, Any]) -> dict[str, Any]:
        relative = PurePosixPath(str(result["path"]))
        if not relative.parts or relative.is_absolute() or ".." in relative.parts:
            raise ResolutionError("candidate workflow path escapes the project")
        sober_dir = self.root / ".sober"
        candidates_dir = sober_dir / "update-vanguard-candidates"
        if sober_dir.is_symlink() or candidates_dir.is_symlink():
            raise ResolutionError("candidate storage path must not follow symlinks")
        content = str(result.pop("content"))
        content_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
        candidate_id = hashlib.sha256(f"{head_sha}:{relative}:{content_sha}".encode()).hexdigest()[:24]
        directory = candidates_dir / candidate_id / Path(*relative.parts).parent
        cursor = candidates_dir
        for part in (candidate_id, *Path(*relative.parts).parent.parts):
            cursor /= part
            if cursor.is_symlink():
                raise ResolutionError("candidate storage path must not traverse symlinks")
        if not directory.resolve().is_relative_to(candidates_dir.resolve()):
            raise ResolutionError("candidate storage path escapes managed state")
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / relative.name
        if target.exists():
            if target.is_symlink() or target.read_text(encoding="utf-8") != content:
                raise ResolutionError("existing candidate artifact differs; preserving it")
        else:
            descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        result["candidate_id"] = candidate_id
        result["candidate_path"] = target.relative_to(self.root).as_posix()
        result["candidate_sha256"] = content_sha
        return result


def _project_identity(root: Path) -> str:
    """Use credential-free origin identity so clones/worktrees share one ledger."""
    try:
        remote = subprocess.check_output(
            ["git", "remote", "get-url", "origin"], cwd=root, text=True,
            stderr=subprocess.DEVNULL, timeout=15,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        remote = ""
    if remote:
        if "://" in remote:
            parsed = urlsplit(remote)
            host, path = parsed.hostname, parsed.path.lstrip("/")
        elif match := re.fullmatch(r"(?:[^@/]+@)?([^:/]+):(.+)", remote):
            host, path = match.group(1), match.group(2)
        else:
            host, path = None, ""
        path = path.removesuffix(".git").strip("/")
        if host and path and ".." not in Path(path).parts:
            return f"git:{host.lower()}/{path.lower()}"
    return str(root.resolve())


def _ledger(root: Path) -> Ledger:
    return Ledger(root / ".sober" / "update-vanguard.sqlite3")


def _source_change_gate(manifest: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    """Authorize only owner-approved source editing for a clean exact SHA."""
    blockers: list[str] = []
    if manifest.get("project", {}).get("authority") != "owner":
        blockers.append("project owner authority is not explicit")
    if manifest.get("policy", {}).get("enabled") is not True:
        blockers.append("update policy is disabled")
    if snapshot.get("worktree_clean") is not True:
        blockers.append("source worktree is dirty")
    source_sha = snapshot.get("head_sha")
    if not isinstance(source_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        blockers.append("full source SHA is unavailable")
    return {
        "allowed": not blockers,
        "source_sha": source_sha,
        "scope": "owner-authorized source editing only",
        "blockers": blockers,
    }


def _plan(snapshot: dict[str, Any], resolutions: list[dict[str, Any]],
          action_resolutions: list[dict[str, Any]] | None = None, *,
          probe_plan_verified: bool = False) -> dict[str, Any]:
    action_resolutions = action_resolutions or []
    # Python runtime resolution contributes to the deploy candidate. Workflow
    # pin resolution is advisory and must never block the local release gate.
    has_resolution_error = any(item.get("error") for item in resolutions)
    has_action_resolution_error = any(item.get("error") for item in action_resolutions)
    changes = [change for item in resolutions if not item.get("error")
               for change in item.get("package_changes", [])]
    changes.extend({"name": item["repository"], "from": item["from_version"],
                    "to": item["to_version"], "manifest": item.get("path")}
                   for result in action_resolutions if not result.get("error")
                   for item in result.get("changes", []))
    has_resolutions = bool(resolutions or action_resolutions)
    package_risk, package_reasons = package_delta(changes) if not has_resolution_error and has_resolutions else (None, [])
    evidence = RiskEvidence(
        package_delta=package_risk, project_imports_affected=None, runtime_delta=None,
        api_delta=None, persistent_data_affected=None, tests_complete=None,
        backup_restore_verified=None, rollback_verified=None, probes_verified=None,
    )
    risk, risk_blockers = classify(evidence)
    merge_gates = evaluate_gates(evidence, risk, "merge")
    deploy_gates = evaluate_gates(evidence, risk, "deploy")
    blocker_details: dict[str, list[str]] = {
        "risk": list(risk_blockers), "package": list(package_reasons), "coverage": [],
        "resolution": [], "request": [], "policy": [],
    }
    advisories: list[str] = []
    coverage_evidence = _coverage_evidence(snapshot)
    if coverage_evidence["status"] != "complete":
        advisories.append("inventory has unresolved coverage; pending items remain visible and are scoped by source impact")
    if has_resolution_error:
        blocker_details["resolution"].append("at least one requested stable resolver failed or is unsupported")
    if has_action_resolution_error:
        advisories.append("GitHub Actions pin resolver failed; workflow findings are informational")
    if not resolutions and snapshot["python_projects"]:
        # A normal source-release plan intentionally skips dependency candidate
        # discovery. Candidate discovery is an explicit PLAN option; requiring
        # it here would turn every source-only release into a dependency-upgrade
        # campaign and block the documented `updates.run` path.
        advisories.append(
            "stable Python candidate discovery was not requested; this is a source-only plan"
        )
    plan = {
        "schema_version": 1, "project": snapshot["project_name"], "head_sha": snapshot["head_sha"],
        "channel": "stable", "risk": risk, "risk_evidence": evidence.to_receipt(),
        "candidates": [{key: value for key, value in item.items() if key != "candidate_lock"}
                       for item in resolutions if not item.get("error")] + [
                           {key: value for key, value in item.items() if key != "content"}
                           for item in action_resolutions if not item.get("error")],
        "code_gate": {"status": "pending", "source_sha": snapshot["head_sha"]},
        "deployment_evidence": {"status": "preflight",
                                "probe_plan_verified": probe_plan_verified},
        "coverage_evidence": coverage_evidence,
        "blockers": [], "blocker_details": blocker_details, "advisories": advisories,
        "risk_reasons": risk_blockers, "package_reasons": package_reasons,
        "merge_gates": merge_gates, "deploy_gates": deploy_gates,
        "auto_merge": False, "auto_deploy": False,
    }
    if snapshot.get("worktree_clean") is not True:
        plan["code_gate"] = {
            "status": "blocked", "source_sha": snapshot["head_sha"],
            "blocker": "working tree has changes not represented by this source SHA",
        }
        blocker_details["source"] = [
            "working tree has changes not represented by this source SHA",
        ]
    # The canonical plan's active gate is phase-aware: before deployment it
    # answers whether the effect is safe to attempt; after deployment it waits
    # for production tests and health receipts before allowing completion.
    blocker_details["gates"] = sorted(set(deploy_gates["blockers"]))
    _refresh_plan_blockers(plan)
    return plan


def _valid_test_receipt(execution: dict[str, Any], expected_sha: str | None,
                        plan: dict[str, Any]) -> bool:
    if (execution.get("status") != "passed" or not isinstance(expected_sha, str)
            or execution.get("source_sha") != expected_sha
            or not isinstance(execution.get("candidate_set_sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", execution["candidate_set_sha256"])
            or _candidate_set_sha256(plan) != execution.get("candidate_set_sha256")):
        return False
    commands = execution.get("declared_gate_commands")
    phases = execution.get("phases")
    if not isinstance(commands, list) or not commands or not isinstance(phases, list):
        return False
    installs = [phase for phase in phases if phase.get("phase") == "install"]
    gate_phases = [phase for phase in phases if phase.get("phase") == "gate"]
    gates = {phase.get("command_index"): phase for phase in gate_phases}
    return (
        len(installs) == 1 and installs[0].get("install_exit_code") == 0
        and installs[0].get("network_fenced") is True
        and len(gate_phases) == len(commands)
        and set(gates) == set(range(len(commands)))
        and all(gates[index].get("exit_code") == 0 for index in range(len(commands)))
    )


def _canonical_suite_passed(plan: dict[str, Any], source_sha: str) -> bool:
    """Return true only for a durable full-suite receipt bound to this SHA."""
    gate = plan.get("code_gate")
    if not isinstance(gate, dict) or gate.get("source_sha") != source_sha:
        return False
    if gate.get("suite_passed") is not True:
        return False
    commands = gate.get("commands")
    if not isinstance(commands, list):
        return False
    return any(
        isinstance(item, dict) and item.get("exit_code") == 0
        and item.get("command") == ["python3", "-m", "ops.ci", "--expect", source_sha]
        for item in commands
    )


def _status_publication_confirmed(plan: dict[str, Any], source_sha: str) -> bool:
    publication = plan.get("status_publication")
    return bool(
        isinstance(publication, dict)
        and publication.get("status") == "confirmed"
        and publication.get("source_sha") == source_sha
        and publication.get("state") == "success"
        and publication.get("exit_code") == 0
    )


def _refresh_plan_gates(plan: dict[str, Any]) -> None:
    try:
        evidence = RiskEvidence(**plan["risk_evidence"])
    except (KeyError, TypeError):
        plan["blockers"] = sorted(set([*plan.get("blockers", []), "canonical risk evidence is malformed"]))
        return
    plan["risk_evidence"] = evidence.to_receipt()
    risk, risk_blockers = classify(evidence)
    deployment = plan.get("deployment_evidence", {})
    probe_plan_verified = (deployment.get("probe_plan_verified")
                           if isinstance(deployment, dict) else None)
    merge_gates = evaluate_gates(evidence, risk, "merge")
    deploy_gates = evaluate_gates(evidence, risk, "deploy",
                                  probe_plan_verified=probe_plan_verified)
    post_deploy_gates = evaluate_gates(evidence, risk, "deploy", phase="post-deploy")
    plan["risk"] = risk
    plan["risk_reasons"] = risk_blockers
    plan["merge_gates"] = merge_gates
    plan["deploy_gates"] = deploy_gates
    plan["post_deploy_gates"] = post_deploy_gates
    # No merge adapter exists yet, so even a matching allowlist cannot claim
    # automatic merge. Automatic deployment requires both the owner-authored
    # risk allowlist and the live, recalculated canonical preflight gate.
    auto_deploy_risks = plan.get("auto_deploy_risks", [])
    plan["auto_merge"] = False
    plan["auto_deploy"] = bool(
        isinstance(auto_deploy_risks, list)
        and risk in auto_deploy_risks
        and deploy_gates.get("allowed") is True
    )
    details = plan.setdefault("blocker_details", {})
    if not isinstance(details, dict):
        details = plan["blocker_details"] = {}
    details["risk"] = list(risk_blockers)
    effect_started = (isinstance(deployment, dict)
                      and deployment.get("status") not in {None, "not_started", "preflight"})
    blockers = ([*merge_gates["blockers"], *post_deploy_gates["blockers"]]
                if effect_started else list(deploy_gates["blockers"]))
    details["gates"] = sorted(set(blockers))
    code_gate = plan.get("code_gate", {})
    details["code_gate"] = ([] if not effect_started or (isinstance(code_gate, dict)
                             and code_gate.get("status") == "passed"
                             and code_gate.get("source_sha") == plan.get("head_sha"))
                             else ["canonical code gate has not passed for this source SHA"])
    publication_required = plan.get("status_publication_required") is True
    details["status_publication"] = (
        [] if (not publication_required or not effect_started or _status_publication_confirmed(
            plan, str(plan.get("head_sha", "")),
        )) else ["required GitHub commit status is not confirmed for this source SHA"]
    )
    _refresh_plan_blockers(plan)


def _refresh_plan_blockers(plan: dict[str, Any]) -> None:
    details = plan.get("blocker_details", {})
    if not isinstance(details, dict):
        return
    # Migrate legacy global coverage blockers into durable advisory evidence.
    # Action readiness is decided by source impact, risk, and action-specific
    # gates; an unrelated discovery gap cannot override that decision.
    legacy_coverage = details.pop("coverage", [])
    if isinstance(legacy_coverage, list) and legacy_coverage:
        advisories = plan.setdefault("advisories", [])
        if isinstance(advisories, list):
            message = "inventory has unresolved coverage; pending items remain visible and are scoped by source impact"
            if message not in advisories:
                advisories.append(message)
    plan["blockers"] = sorted({
        message for messages in details.values()
        if isinstance(messages, list)
        for message in messages if isinstance(message, str) and message
    })
    plan["gate"] = {"status": "blocked" if plan["blockers"] else "ready",
                     "blockers": list(plan["blockers"])}


def _coverage_evidence(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Keep inventory gaps durable without making unrelated gaps a global gate."""
    pending = snapshot.get("pending", [])
    if not isinstance(pending, list):
        pending = []
    return {
        "status": "complete" if snapshot.get("coverage") == "complete" else "pending",
        "pending": sorted({item for item in pending if isinstance(item, str)}),
        "enforcement": "source-impact-scoped",
    }


def _candidate_change_count(candidates: Any) -> int | None:
    """Count the exact candidate set conservatively for the policy ceiling."""
    if not isinstance(candidates, list):
        return None
    total = 0
    for candidate in candidates:
        if not isinstance(candidate, dict):
            return None
        if "changed_package_count" in candidate:
            count = candidate["changed_package_count"]
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                return None
        elif "changes" in candidate:
            changes = candidate["changes"]
            if not isinstance(changes, list):
                return None
            count = len(changes)
        else:
            return None
        total += count
    return total


def _candidate_policy(plan: dict[str, Any], policy: dict[str, Any]) -> tuple[int | None, int | None, str | None]:
    count = _candidate_change_count(plan.get("candidates", []))
    limit = policy.get("limits", {}).get("max_changed_packages")
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        return count, limit if isinstance(limit, int) else None, "candidate policy limit is invalid"
    if count is None:
        return None, limit, "candidate change count is malformed"
    if count > limit:
        return count, limit, f"candidate changes {count} packages; policy limit is {limit}"
    return count, limit, None


def _is_deploy_key(key: Any, sha: Any) -> bool:
    """`deploy:<sha>` or one of its later generations `deploy:<sha>:<n>`."""
    return (isinstance(key, str) and isinstance(sha, str)
            and (key == f"deploy:{sha}" or key.startswith(f"deploy:{sha}:")))


def _deploy_key(ledger: Ledger, job_id: str, sha: str) -> str:
    """Key of the current deployment effect for `sha`: its newest generation."""
    keys = [e["effect_key"] for e in ledger.effects(job_id) if _is_deploy_key(e["effect_key"], sha)]
    return keys[-1] if keys else f"deploy:{sha}"


def _applied_deploy_sha(effect: dict[str, Any]) -> str | None:
    result = effect.get("result") if isinstance(effect.get("result"), dict) else {}
    snapshot = result.get("snapshot") if isinstance(result.get("snapshot"), dict) else {}
    if (effect.get("kind") == "updates.deploy" and effect.get("state") == "applied"
            and result.get("outcome") == "applied" and isinstance(snapshot.get("source_sha"), str)):
        return snapshot["source_sha"]
    return None


def _superseding_deploy(ledger: Ledger, job_id: str, effect: dict[str, Any]) -> str | None:
    """SHA of an applied deployment of ANOTHER source recorded after `effect`, if any.

    Ledger order (`created_at`) proves the later deploy replaced this one; the caller
    also needs the read-only observer to say this SHA is not live before acting on it.
    """
    own = _applied_deploy_sha(effect)
    effects = ledger.effects(job_id)
    keys = [e["effect_key"] for e in effects]
    if own is None or effect.get("effect_key") not in keys:
        return None
    for later in effects[keys.index(effect["effect_key"]) + 1:]:
        sha = _applied_deploy_sha(later)
        if sha is not None and sha != own:
            return sha
    return None


def _probe_plan_verified(manifest: dict[str, Any]) -> bool:
    """Accept only non-empty, repo-declared HTTP paths; never shell commands or URLs."""
    probes = manifest.get("deployment", {}).get("probes", [])
    if not isinstance(probes, list) or not probes:
        return False
    for probe in probes:
        if (not isinstance(probe, str) or not probe.startswith("/") or probe.startswith("//")
                or "\\" in probe or "#" in probe or any(ord(char) < 32 for char in probe)):
            return False
        path = probe.partition("?")[0]
        if any(part in {".", ".."} for part in path.split("/")):
            return False
        if not re.fullmatch(r"/[A-Za-z0-9._~/-]+(?:\?[A-Za-z0-9._~=&-]*)?", probe):
            return False
    return True


def _release_acceptance_passed(plan: Any, job: Any) -> bool:
    """Judge this deployed release by its action-specific post-deploy gate.

    The aggregate plan can retain unrelated inventory blockers (for example,
    unsupported dependency ecosystems). Those remain visible and block their
    own actions, but do not invalidate an exact-SHA release whose production
    probes and canonical post-deploy suite passed.
    """
    if not isinstance(plan, dict) or not isinstance(job, dict):
        return False
    head_sha = job.get("head_sha")
    code_gate = plan.get("code_gate")
    deployment = plan.get("deployment_evidence")
    post_gate = plan.get("post_deploy_gates")
    return bool(
        isinstance(head_sha, str)
        and plan.get("head_sha") == head_sha
        and isinstance(code_gate, dict)
        and code_gate.get("status") == "passed"
        and code_gate.get("source_sha") == head_sha
        and isinstance(deployment, dict)
        and deployment.get("status") == "deployed"
        and deployment.get("source_sha") == head_sha
        and deployment.get("probes_verified") is True
        and isinstance(post_gate, dict)
        and post_gate.get("allowed") is True
        and job.get("state") != "uncertain"
    )


# Process identity lives in one module shared by every owner/lease check (Linux and macOS).
_process_identity = process_identity


def _orphan_evidence(gate: dict[str, Any], now: float) -> dict[str, Any] | None:
    """Return why a running code gate is provably orphaned, or None."""
    owner = gate.get("owner")
    if isinstance(owner, dict):
        reason = owner_gone(owner)  # None: alive or undecidable here; never guess
        return {"reason": reason, "owner": owner} if reason else None
    from datetime import datetime
    try:
        started = datetime.fromisoformat(str(gate.get("started_at"))).timestamp()
    except ValueError:
        return None
    age = now - started
    if age <= _LEGACY_ORPHAN_AGE_S:
        return None
    return {"reason": f"legacy claim without owner, running for {int(age)} s", "started_at": gate["started_at"]}


def _utc_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _git_snapshot(root: Path) -> dict[str, Any]:
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, timeout=15, check=False)
    status = git_worktree_status(root)
    return {"head_sha": head.stdout.strip() if head.returncode == 0 else None,
            "clean": status == "" if status is not None else False}


def _run_code_gate_command(command: list[str], root: Path) -> tuple[int, str]:
    completed = subprocess.run(command, cwd=root, stdin=subprocess.DEVNULL, capture_output=True,
                               text=True, encoding="utf-8", errors="replace", timeout=1800,
                               check=False)
    return completed.returncode, (completed.stdout or "") + (completed.stderr or "")


def _candidate_set_sha256(plan: dict[str, Any]) -> str | None:
    """Hash the exact candidate files using the executor's receipt format."""
    candidates = plan.get("candidates")
    if not isinstance(candidates, list):
        return None
    files: list[dict[str, str]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            return None
        if candidate.get("project_manifest") and candidate.get("files"):
            manifest = PurePosixPath(str(candidate["project_manifest"]))
            names = candidate["files"]
            digest = candidate.get("new_lock_sha256")
            if (manifest.is_absolute() or ".." in manifest.parts
                    or not isinstance(names, list) or not names):
                return None
            relative = PurePosixPath(*manifest.parts[:-1]) / str(names[0])
            if (relative.is_absolute() or ".." in relative.parts or not isinstance(names[0], str)
                    or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
                return None
            files.append({"path": str(relative), "sha256": digest})
        elif candidate.get("path") and candidate.get("changed") is True:
            path, digest = candidate.get("path"), candidate.get("candidate_sha256")
            relative = PurePosixPath(str(path))
            if (relative.is_absolute() or ".." in relative.parts
                    or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
                return None
            files.append({"path": str(relative), "sha256": digest})
    if not files or len({item["path"] for item in files}) != len(files):
        return None
    return hashlib.sha256(json.dumps(
        sorted(files, key=lambda item: item["path"]), sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
