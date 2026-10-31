"""PARADIGMA: one bounded PR gate run through the project's declared merge adapter.

``harness-agent gate --pr N`` replaces the coordinator's manual routine:
wait (bounded) until GitHub shows the pushed head, check out that exact head
in a detached temporary worktree, run the project's merge command there, and,
only when its output says the deployment outcome is uncertain, run the
project's recover command once and the merge once more. Nothing here knows a
project: the commands, interpreter, environment and the uncertain/job
patterns come from ``[gates.pr]`` in the head's ``.sober/updates.toml``. The
head worktree is the trust boundary the merge adapter already runs in, so its
manifest is read there (a PR that adds ``[gates.pr]`` can be gated by it).

Before the merge, every file of the PR must be claimed by the mission that
holds the PR branch and by no other (``claim_guard.evaluate``). This is the one
point that sees work from clones and runners that commit without hooks.

Success removes the temporary worktree; any failure preserves it. The mission
journal gets ``gate_started`` and ``gate_passed``/``gate_failed`` with PR, SHA
and a typed reason; ``--report`` gets a first line ``STATUS: ENTREGUE`` or
``STATUS: BLOQUEADO`` plus a bounded diagnostic tail.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
from typing import Any, Callable, Sequence
from uuid import uuid4

from .ledger import Ledger, _derived_event_id
from .manifest import ManifestError, load_manifest

EXIT_PASSED = 0
EXIT_BLOCKED = 1
EXIT_REFUSED = 2
HEAD_WAIT_S = 60.0
_TAIL_LINES = 40
ClaimCheck = Callable[[Path, list, "str | None"], Any]

Runner = Callable[..., tuple[int, str]]


class GateConfigError(ValueError):
    """The project does not declare a usable ``[gates.pr]`` adapter."""


@dataclass(frozen=True)
class GateAdapter:
    python: str
    merge: tuple[str, ...]
    recover: tuple[str, ...]
    env: dict[str, str]
    uncertain_output: re.Pattern[str] | None
    uncertain_exit_codes: frozenset[int]
    job_output: re.Pattern[str] | None
    timeout: int
    # Run in the canonical checkout after a durable merge (e.g. fast-forward it and
    # install on the host); a failure is recorded, never reported as a failed merge.
    post_merge: tuple[tuple[str, ...], ...] = ()

    @classmethod
    def load(cls, root: Path) -> "GateAdapter":
        try:
            manifest = load_manifest(root)
        except ManifestError as exc:
            raise GateConfigError(str(exc)) from exc
        pr = ((manifest or {}).get("gates") or {}).get("pr")
        if not isinstance(pr, dict):
            raise GateConfigError(
                "the project manifest (.sober/updates.toml) declares no [gates.pr] merge adapter; "
                "add python, merge and (for uncertain deploys) recover, uncertain_output and job_output")
        return cls(
            python=pr["python"], merge=tuple(pr["merge"]), recover=tuple(pr.get("recover", ())),
            env=dict(pr.get("env", {})),
            uncertain_output=re.compile(pr["uncertain_output"]) if pr.get("uncertain_output") else None,
            uncertain_exit_codes=frozenset(pr.get("uncertain_exit_codes", ())),
            job_output=re.compile(pr["job_output"]) if pr.get("job_output") else None,
            timeout=pr.get("timeout_seconds", 7200),
            post_merge=tuple(tuple(command) for command in pr.get("post_merge", ())),
        )

    def uncertain(self, code: int, output: str) -> bool:
        return code != 0 and (code in self.uncertain_exit_codes
                              or bool(self.uncertain_output and self.uncertain_output.search(output)))

    def job(self, output: str) -> str | None:
        found = list(self.job_output.finditer(output)) if self.job_output else []
        if not found:
            return None
        match = found[-1]
        job = match.group(1) if match.lastindex else match.group(0)
        return job if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", job) else None


def run_command(argv: Sequence[str], *, cwd: Path, env: dict[str, str] | None = None,
                timeout: float = 120) -> tuple[int, str]:
    try:
        process = subprocess.run(list(argv), cwd=cwd, env=env, timeout=timeout, text=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout if isinstance(exc.stdout, str) else ""
        return 124, output + f"\n[timeout after {timeout:.0f}s]"
    except OSError as exc:
        return 127, f"{type(exc).__name__}: {exc}"
    return process.returncode, process.stdout


def _expand(template: Sequence[str], values: dict[str, str]) -> list[str]:
    return [item.format_map(values) for item in template]


def _tail(text: str) -> str:
    return "\n".join(text.strip().splitlines()[-_TAIL_LINES:])


class _Gate:
    def __init__(self, *, pr: int, repo: Path, mission: int | None, ledger: Ledger | None,
                 runner: Runner, sleep: Callable[[float], None], clock: Callable[[], float],
                 head_wait: float, temp_root: Path, claim_check: ClaimCheck):
        self.pr, self.repo, self.mission, self.ledger = pr, repo, mission, ledger
        self.claim_check = claim_check
        self.run, self.sleep, self.clock = runner, sleep, clock
        self.head_wait, self.temp_root = head_wait, temp_root
        self.run_id = uuid4().hex
        self.head: str | None = None
        self.branch: str | None = None
        self.worktree: Path | None = None
        self.log: list[str] = []
        self.attempt = 0

    def note(self, line: str) -> None:
        self.log.append(line)

    def event(self, event_type: str, **checkpoint: Any) -> None:
        if self.ledger is None or self.mission is None:
            return
        checkpoint = {"stage": "gate", "writer": "gate", "pr_number": self.pr, **checkpoint}
        if self.head:
            checkpoint["head_sha"] = self.head
        if self.branch:
            checkpoint["branch"] = self.branch
        if self.worktree is not None:
            checkpoint["worktree"] = str(self.worktree)
        if self.attempt:
            checkpoint["attempt"] = self.attempt
        self.ledger.record_mission_event(
            job_id=None, source_sha=None, mission_id=self.mission,
            event_id=_derived_event_id("gate", self.run_id, event_type), event_type=event_type,
            checkpoint=checkpoint)

    def pr_view(self) -> dict[str, Any] | None:
        code, output = self.run(["gh", "pr", "view", str(self.pr), "--json",
                                 "headRefOid,headRefName,state,mergeCommit"], cwd=self.repo, timeout=60)
        if code != 0:
            self.note(f"gh pr view #{self.pr} failed ({code}): {_tail(output)}")
            return None
        try:
            data = json.loads(output)
        except ValueError:
            self.note("gh pr view returned invalid JSON")
            return None
        return data if isinstance(data, dict) else None

    def remote_head(self, branch: str) -> str | None:
        code, output = self.run(["git", "ls-remote", "origin", f"refs/heads/{branch}"], cwd=self.repo, timeout=60)
        if code != 0:
            return None
        fields = output.split()
        return fields[0] if fields and re.fullmatch(r"[0-9a-f]{40}", fields[0]) else None

    def wait_for_head(self) -> tuple[str, str] | None:
        """GitHub's PR head equals the pushed branch tip, within a bounded backoff."""
        deadline, delay = self.clock() + self.head_wait, 2.0
        while True:
            view = self.pr_view()
            if view is not None and view.get("state") != "OPEN":
                self.note(f"PR #{self.pr} is {view.get('state')}, not OPEN")
                return None
            head = (view or {}).get("headRefOid")
            branch = (view or {}).get("headRefName")
            if isinstance(head, str) and isinstance(branch, str) and branch:
                pushed = self.remote_head(branch)
                if pushed == head:
                    return head, branch
                self.note(f"GitHub head {head[:12]} != pushed {(pushed or '?')[:12]} on {branch}")
            remaining = deadline - self.clock()
            if remaining <= 0:
                return None
            self.sleep(min(delay, remaining))
            delay = min(delay * 2, 16.0)

    def checkout(self, head: str, branch: str) -> bool:
        code, output = self.run(["git", "fetch", "-q", "origin", f"refs/heads/{branch}"], cwd=self.repo, timeout=300)
        if code != 0:
            self.note(f"git fetch failed: {_tail(output)}")
            return False
        self.temp_root.mkdir(parents=True, exist_ok=True)
        path = Path(tempfile.mkdtemp(prefix=f"harness-gate-{self.pr}-{head[:12]}-", dir=self.temp_root))
        path.rmdir()
        code, output = self.run(["git", "worktree", "add", "--detach", str(path), head], cwd=self.repo, timeout=300)
        if code != 0:
            self.note(f"git worktree add failed: {_tail(output)}")
            return False
        self.worktree = path
        code, local = self.run(["git", "rev-parse", "HEAD"], cwd=path)
        status_code, dirty = self.run(["git", "status", "--porcelain"], cwd=path)
        if code != 0 or local.strip() != head or status_code != 0 or dirty.strip():
            self.note("temporary worktree is not a clean checkout of the PR head")
            return False
        return True

    def claims_refused(self) -> tuple[str, str] | None:
        """Every file of the PR must be claimed by the mission holding its branch, and by no other.

        This is the one point every executor passes through, including clones and
        runners that commit without hooks. An unbound project is not adopted and
        passes; a diff that cannot be read is not measured and blocks.
        """
        code, output = self.run(["gh", "pr", "diff", str(self.pr), "--name-only"], cwd=self.repo, timeout=120)
        if code != 0:
            self.note(f"gh pr diff #{self.pr} failed ({code}): {_tail(output)}")
            return "ClaimsNotMeasured", "transient"
        files = [line.strip() for line in output.splitlines() if line.strip()]
        decision = self.claim_check(self.repo, files, self.branch)
        if decision.status == "not_adopted":
            self.note("claims not enforced: " + "; ".join(decision.reasons))
            return None
        if decision.status != "allow":
            self.note("claims refused the merge:\n" + "\n".join(f"  - {r}" for r in decision.reasons))
            return "ClaimsRefused", "auto_correctable"
        return None

    def remove_worktree(self) -> bool:
        if self.worktree is None:
            return True
        code, output = self.run(["git", "worktree", "remove", str(self.worktree)], cwd=self.repo, timeout=120)
        if code != 0:
            self.note(f"temporary worktree kept: {_tail(output)}")
            return False
        self.worktree = None
        return True

    def adapter_env(self, adapter: GateAdapter, values: dict[str, str]) -> dict[str, str]:
        env = dict(os.environ)
        env.update({key: value.format_map(values) for key, value in adapter.env.items()})
        return env

    def merge_with_one_recovery(self, adapter: GateAdapter) -> tuple[bool, str, str]:
        """(passed, error_type, classification). Recover at most once, retry merge at most once."""
        assert self.worktree is not None and self.head is not None
        values = {"python": adapter.python, "pr": str(self.pr), "worktree": str(self.worktree),
                  "repo": str(self.repo), "home": str(Path.home()), "head_sha": self.head}
        env = self.adapter_env(adapter, values)
        recovered = False
        while True:
            self.attempt += 1
            code, output = self.run(_expand(adapter.merge, values), cwd=self.worktree, env=env,
                                    timeout=adapter.timeout)
            self.note(f"merge attempt {self.attempt} exited {code}:\n{_tail(output)}")
            if code == 0:
                return True, "", ""
            if not adapter.uncertain(code, output):
                return False, "MergeFailed", "unknown"
            if recovered:
                return False, "DeployUncertainAfterRecover", "uncertain_effect"
            job = adapter.job(output)
            if job is None or not adapter.recover:
                self.note("deploy uncertain but no job ID or recover command to reconcile it")
                return False, "DeployUncertainUnreconciled", "uncertain_effect"
            code, output = self.run(_expand(adapter.recover, {**values, "job": job}), cwd=self.worktree,
                                    env=env, timeout=adapter.timeout)
            self.note(f"recover {job} exited {code}:\n{_tail(output)}")
            recovered = True
            if code != 0:
                return False, "RecoverFailed", "uncertain_effect"
            view = self.pr_view()
            if view is None or view.get("state") != "OPEN" or view.get("headRefOid") != self.head:
                # Already merged (the uncertain part was the post-merge release) or the head
                # moved: a second merge cannot help; the recovered job needs the owner's look.
                self.note("PR is no longer the open head that was gated; merge not retried")
                return False, "MergedReleaseRecovered", "external_proof"

    def report(self, path: Path | None, passed: bool, reason: str, merge_sha: str | None) -> None:
        if path is None:
            return
        lines = [f"STATUS: {'ENTREGUE' if passed else 'BLOQUEADO'}",
                 f"PR: #{self.pr}", f"HEAD: {self.head or '?'}", f"BRANCH: {self.branch or '?'}"]
        if merge_sha:
            lines.append(f"MERGE: {merge_sha}")
        if reason:
            lines.append(f"MOTIVO: {reason}")
        lines.append(f"WORKTREE: {self.worktree or 'removida'}")
        lines += ["", "## Diagnóstico", *self.log]
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{self.run_id}")
        temporary.write_text("\n".join(lines) + "\n", encoding="utf-8")
        temporary.replace(path)  # waiters never read a partial first line

    def execute(self, report: Path | None, release_claims: Callable[[str, str], None],
                release_resources: Callable[[str], dict] | None = None) -> int:
        self.event("gate_started", status="running", next_step="merge")
        found = self.wait_for_head()
        if found is None:
            return self.finish(report, False, "HeadNotPublished", "transient", None)
        self.head, self.branch = found
        if not self.checkout(*found):
            return self.finish(report, False, "CheckoutFailed", "transient", None)
        try:
            adapter = GateAdapter.load(self.worktree)
        except GateConfigError as exc:
            self.note(f"REFUSED: {exc}")
            self.finish(report, False, "GateNotConfigured", "auto_correctable", None)
            return EXIT_REFUSED
        refused = self.claims_refused()
        if refused is not None:
            return self.finish(report, False, *refused, None)
        passed, error, classification = self.merge_with_one_recovery(adapter)
        if not passed:
            return self.finish(report, False, error, classification, None)
        view = self.pr_view() or {}
        merge_sha = (view.get("mergeCommit") or {}).get("oid")
        if view.get("state") != "MERGED" or not isinstance(merge_sha, str):
            self.note("merge adapter exited 0 but the PR is not MERGED")
            return self.finish(report, False, "MergeNotObserved", "uncertain_effect", None)
        try:
            release_claims(self.branch, merge_sha)
        except Exception as exc:  # the merge is durable; reconcile with `harness-agent release --merged-pr`
            self.note(f"claims not released ({type(exc).__name__}); run harness-agent release --merged-pr {self.pr}")
        if release_resources is not None:
            # The mission's `Drop`: its worktrees go at the merge, not at the next daily sweep.
            try:
                released = release_resources(self.branch)
                removed = [w["worktree"] for w in released.get("worktrees", []) if w.get("removed")]
                kept = [(w["worktree"], w.get("refused")) for w in released.get("worktrees", [])
                        if not w.get("removed")]
                self.note(f"released worktrees of {self.branch}: removed {removed}; kept {kept}")
            except Exception as exc:  # the merge is durable; the daily collector is the safety net
                self.note(f"resources of {self.branch} not released ({type(exc).__name__}: {exc})")
        self.post_merge(adapter, merge_sha)
        if not self.remove_worktree():
            return self.finish(report, False, "WorktreeCleanupFailed", "auto_correctable", merge_sha)
        return self.finish(report, True, "", "", merge_sha)

    def post_merge(self, adapter: GateAdapter, merge_sha: str) -> bool:
        """Converge the host on the merged code; stops at the first failing command."""
        values = {"python": adapter.python, "pr": str(self.pr), "repo": str(self.repo),
                  "home": str(Path.home()), "merge_sha": merge_sha}
        env = self.adapter_env(adapter, values)
        for command in adapter.post_merge:
            code, output = self.run(_expand(command, values), cwd=self.repo, env=env, timeout=adapter.timeout)
            self.note(f"post-merge {' '.join(command[:3])} exited {code}:\n{_tail(output)}")
            if code != 0:
                self.event("blocked", status="blocked", error_type="PostMergeFailed",
                           classification="auto_correctable", next_step="retry")
                return False
        return True

    def finish(self, report: Path | None, passed: bool, error: str, classification: str,
               merge_sha: str | None) -> int:
        if passed:
            self.event("gate_passed", status="completed", next_step="complete")
        else:
            self.event("gate_failed", status="blocked", error_type=error, classification=classification,
                       next_step="diagnose")
        self.report(report, passed, error, merge_sha)
        return EXIT_PASSED if passed else EXIT_BLOCKED


def run_gate(*, pr: int, repo: Path, report: Path | None = None, mission: int | None = None,
             ledger: Ledger | None = None, project: str | None = None, runner: Runner = run_command,
             sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic,
             head_wait: float = HEAD_WAIT_S, temp_root: Path | None = None,
             claim_check: ClaimCheck | None = None) -> int:
    """Gate one PR; ``repo`` is the canonical checkout whose ``origin`` hosts the PR."""
    temp_root = temp_root or Path(os.environ.get("TMPDIR") or Path.home() / "tmp")
    if claim_check is None:
        from .claim_guard import evaluate

        def claim_check(root: Path, files: list[str], branch: str | None) -> Any:
            return evaluate(root, files, branch=branch)
    gate = _Gate(pr=pr, repo=repo, mission=mission, ledger=ledger, runner=runner, sleep=sleep, clock=clock,
                 head_wait=head_wait, temp_root=temp_root, claim_check=claim_check)

    def release_claims(branch: str, merge_sha: str) -> None:
        if ledger is not None and project is not None:
            ledger.release_merged_branch(project_root=project, branch=branch, pr_number=pr,
                                         merge_sha=merge_sha, released_by="harness-gate")

    def release_resources(branch: str) -> dict:
        from .worktree_gc import release_branch_resources

        return release_branch_resources(repo, ledger.path if ledger is not None else None, branch)

    return gate.execute(report, release_claims, release_resources)
