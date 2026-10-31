"""PARADIGMA: máquina de estados — o ciclo de vida de uma missão é um fold do seu diário.

A mission's lifecycle state is derived from its append-only event journal
(``update_mission_events``), never from wall-clock age or by re-reading git and
GitHub. Facts that already exist keep their source: a merge releases the
mission's claims with reason ``merged``, an owner discard with ``discarded``.
The lifecycle facts that had no record are ``checkpoint`` events whose ``stage``
names them: ``pr_closed``, ``merged_pr``, ``parked``, ``unparked``, ``discarded``, ``collected``
and ``stalled``.

States: ``active`` until a terminal fact; ``merged``, ``closed`` and
``discarded`` are terminal and collectable; ``collected`` is final. ``parked``
and ``stalled`` are flags over ``active``: a parked mission is never collected,
and stalled is only a signal (time may raise it; time never collects). A park
names its ``reason`` and the ``resume_on`` condition that ends it (``pr:N``,
``claim:N`` or ``date:YYYY-MM-DD``), so the reconciler can say when it is due;
a park with no condition stops the work with nothing to restart it.
Recording a transition the current state does not allow raises, so collectors
act on states instead of guessing.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import uuid

from .ledger import Ledger

LIFECYCLE_STAGES = frozenset({"pr_closed", "merged_pr", "parked", "unparked", "discarded", "collected",
                              "stalled"})
TERMINAL = frozenset({"merged", "closed", "discarded"})


class InvalidTransition(ValueError):
    """The mission's current state does not allow this lifecycle event."""


@dataclass(frozen=True)
class MissionState:
    mission_id: int
    state: str = "active"
    parked: bool = False
    stalled: bool = False
    pr_number: int | None = None
    last_event_at: float | None = None
    park_reason: str | None = None
    resume_on: str | None = None

    @property
    def collectable(self) -> bool:
        return self.state in TERMINAL and not self.parked

    def as_dict(self) -> dict[str, Any]:
        return {"mission_id": self.mission_id, "state": self.state, "parked": self.parked,
                "stalled": self.stalled, "pr_number": self.pr_number,
                "last_event_at": self.last_event_at, "collectable": self.collectable,
                "park_reason": self.park_reason, "resume_on": self.resume_on}


def fold(mission_id: int, events: list[dict[str, Any]]) -> MissionState:
    """Replay the journal in order into the mission's current state."""
    state, parked, stalled, pr_number, last = "active", False, False, None, None
    park_reason = resume_on = None
    for event in events:
        last = event.get("created_at", last)
        kind = event.get("event_type")
        checkpoint = event.get("checkpoint") or {}
        stage = checkpoint.get("stage")
        if isinstance(checkpoint.get("pr_number"), int):
            pr_number = checkpoint["pr_number"]
        if kind == "claim_released" and checkpoint.get("release_reason") in {"merged", "discarded"}:
            if state == "active" or (state == "closed" and checkpoint["release_reason"] == "discarded"):
                state = checkpoint["release_reason"]
            continue
        if kind == "checkpoint" and stage in LIFECYCLE_STAGES:
            if stage == "parked":
                parked, park_reason, resume_on = True, checkpoint.get("reason"), checkpoint.get("resume_on")
            elif stage == "unparked":
                parked, park_reason, resume_on = False, None, None
            elif stage == "pr_closed" and state == "active":
                state = "closed"
            elif stage == "merged_pr" and state == "active":
                state = "merged"  # owner-recorded merge of a mission with no claims to release
            elif stage == "discarded" and state in {"active", "closed"}:
                state = "discarded"
            elif stage == "collected" and state in TERMINAL:
                state = "collected"
            elif stage == "stalled":
                stalled = True
            continue
        stalled = False  # any other activity means the mission moved again
    return MissionState(mission_id, state, parked, stalled, pr_number, last, park_reason, resume_on)


def state(ledger: Ledger, mission_id: int) -> MissionState:
    return fold(mission_id, ledger.mission_events(mission_id))


def _allowed(current: MissionState, stage: str) -> bool:
    if stage == "parked":
        # A closed mission can still be kept (its PR may reopen); a park recorded without a
        # resume condition gets one in place, never through unpark, which would leave the
        # mission collectable in between.
        return current.state in {"active", "closed"} and (not current.parked or not current.resume_on)
    if stage == "unparked":
        return current.parked
    if stage in {"pr_closed", "merged_pr"}:
        return current.state == "active" and not (stage == "merged_pr" and current.parked)
    if stage == "discarded":
        return current.state in {"active", "closed"} and not current.parked
    if stage == "collected":
        return current.collectable
    if stage == "stalled":
        return current.state == "active" and not current.parked and not current.stalled
    return False


def record(ledger: Ledger, mission_id: int, stage: str, *, pr_number: int | None = None,
           branch: str | None = None, head_sha: str | None = None,
           facts: dict[str, Any] | None = None) -> MissionState:
    """Append one lifecycle fact after checking the current state allows it."""
    if stage not in LIFECYCLE_STAGES:
        raise InvalidTransition(f"unknown lifecycle stage {stage!r}")
    if stage == "parked" and not {"reason", "resume_on"} <= set(facts or {}):
        raise ValueError("a park names its reason and its resume_on condition (pr:N, claim:N or date:YYYY-MM-DD)")
    current = state(ledger, mission_id)
    if not _allowed(current, stage):
        raise InvalidTransition(
            f"mission {mission_id} is {current.state}{' (parked)' if current.parked else ''}; "
            f"{stage} is not allowed")
    checkpoint: dict[str, Any] = {"stage": stage, "status": "completed"}
    if pr_number is not None:
        checkpoint["pr_number"] = pr_number
    if branch is not None:
        checkpoint["branch"] = branch
    if head_sha is not None:
        checkpoint["head_sha"] = head_sha
    checkpoint.update(facts or {})
    ledger.record_mission_event(job_id=None, source_sha=None, mission_id=mission_id,
                                event_id=uuid.uuid4().hex, event_type="checkpoint", checkpoint=checkpoint)
    return state(ledger, mission_id)


def park(ledger: Ledger, mission_id: int, *, reason: str, resume_on: str) -> MissionState:
    """Park the mission with the reason and the condition that resumes it."""
    return record(ledger, mission_id, "parked", facts={"reason": reason.strip(), "resume_on": resume_on})


def read_states(ledger_path: Path | None, mission_ids: set[int]) -> dict[int, MissionState]:
    """Fold each mission from a read-only connection; collectors never migrate the ledger."""
    import json
    import sqlite3

    if ledger_path is None or not ledger_path.is_file() or not mission_ids:
        return {}
    conn = sqlite3.connect(f"file:{ledger_path}?mode=ro", uri=True)
    try:
        events: dict[int, list[dict[str, Any]]] = {mission: [] for mission in mission_ids}
        marks = ",".join("?" * len(mission_ids))
        for mission, raw, created in conn.execute(
                f"SELECT mission_id,event_json,created_at FROM update_mission_events "
                f"WHERE mission_id IN ({marks}) ORDER BY created_at,event_id", sorted(mission_ids)):
            event = json.loads(raw)
            event["created_at"] = created
            events[mission].append(event)
    finally:
        conn.close()
    return {mission: fold(mission, items) for mission, items in events.items()}


def owners(ledger_path: Path | None, claims: list[dict] | None) -> tuple[dict[str, int], dict[str, int]]:
    """The one mission per branch (its branch claims, held or released) and the latest per
    worktree path (lifecycle events that name one, e.g. an adopted detached worktree).

    A branch claimed by two missions has no owner: picking one would let a terminal mission
    collect the other's worktree. Claims of a mission this ledger does not hold are ignored,
    since mission ids are per ledger and the same id elsewhere is a different mission."""
    import json
    import sqlite3

    known: set[int] | None = None
    by_worktree: dict[str, int] = {}
    if ledger_path is not None and ledger_path.is_file():
        conn = sqlite3.connect(f"file:{ledger_path}?mode=ro", uri=True)
        try:
            known = {int(row[0]) for row in conn.execute("SELECT mission_id FROM update_missions")}
            for mission, raw in conn.execute(
                    "SELECT mission_id,event_json FROM update_mission_events WHERE event_type='checkpoint'"):
                worktree = (json.loads(raw).get("checkpoint") or {}).get("worktree")
                if isinstance(worktree, str):
                    by_worktree[worktree] = max(by_worktree.get(worktree, 0), int(mission))
        finally:
            conn.close()
    holders: dict[str, set[int]] = {}
    claimants: dict[str, set[int]] = {}
    for claim in claims or []:
        mission = int(claim["mission_id"])
        if claim["kind"] == "branch" and (known is None or mission in known):
            claimants.setdefault(claim["target"], set()).add(mission)
            if claim.get("released_at") is None:
                holders.setdefault(claim["target"], set()).add(mission)
    by_branch = {}
    for branch, missions in claimants.items():
        # An active branch claim is exclusive, so its holder is the owner; with every claim
        # released, only a branch one mission ever claimed has one.
        candidates = holders.get(branch) or missions
        if len(candidates) == 1:
            by_branch[branch] = next(iter(candidates))
    return by_branch, by_worktree


def adopt_discarded(ledger: Ledger, *, title: str, project: str, branch: str | None,
                    worktree: str) -> MissionState:
    """Give an ownerless, abandoned worktree a mission and record the owner-approved discard."""
    mission = ledger.create_mission(title)
    if branch:
        ledger.acquire_claims(project_root=project, mission_id=mission, holder=branch,
                              targets=[("branch", branch)])
        ledger.release_claims(mission_id=mission, project_root=project, reason="discarded",
                              released_by="harness-worktree-gc", holder=branch, owner_discard=True)
    ledger.record_mission_event(
        job_id=None, source_sha=None, mission_id=mission, event_id=uuid.uuid4().hex,
        event_type="checkpoint",
        checkpoint={"stage": "discarded", "status": "completed", "worktree": worktree,
                    **({"branch": branch} if branch else {})})
    return state(ledger, mission)


def mark_stalled(ledger: Ledger, *, idle_days: float, now: float | None = None) -> list[int]:
    """Signal (never collect) every active, unparked mission with no event for ``idle_days``."""
    import sqlite3
    import time

    now = time.time() if now is None else now
    conn = sqlite3.connect(f"file:{ledger.path}?mode=ro", uri=True)
    try:
        missions = conn.execute("SELECT mission_id,created_at FROM update_missions").fetchall()
    finally:
        conn.close()
    marked = []
    for mission, created in missions:
        current = state(ledger, int(mission))
        last = current.last_event_at or created
        if _allowed(current, "stalled") and (now - last) / 86400 >= idle_days:
            record(ledger, int(mission), "stalled")
            marked.append(int(mission))
    return marked


def default_worktree_root() -> Path:
    """Where missions' worktrees live; the collectors' archive sits beside them."""
    return Path.home() / "dev" / "worktrees"


def open_mission(ledger: Ledger, root: Path, *, title: str, branch: str, paths: list[str],
                 base: str = "origin/main", worktree_root: Path | None = None,
                 project: str | None = None, checkout: Path | None = None) -> dict[str, Any]:
    """Ownership from birth: mission, worktree on a new branch, claims and an `opened` event.

    A worktree created this way always has an owner, so the transition releases it and the
    collectors never have to adopt it. A branch name that exists, or ever had a PR, is refused:
    reusing a merged branch name recreates an orphan ref.

    ``checkout`` names an existing clone of the same remote where the work happens (a task
    runner's isolated clone): no worktree is created, and the `opened` event records the
    clone, so the mission still owns its checkout from birth.
    """
    import re
    import subprocess

    from .agent import project_identity

    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,127}", branch) or ".." in branch.split("/"):
        raise ValueError(f"invalid branch name {branch!r}")

    def git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=300)

    if git("fetch", "-q", "origin").returncode != 0:
        raise ValueError("could not fetch origin; the new branch must start from the current base")
    if git("rev-parse", "-q", "--verify", f"refs/heads/{branch}").returncode == 0 or \
            git("ls-remote", "--exit-code", "--heads", "origin", branch).returncode == 0:
        raise ValueError(f"branch {branch!r} already exists; start new work on a new branch")
    prs = subprocess.run(["gh", "pr", "list", "--state", "all", "--head", branch, "--json", "number"],
                         cwd=root, capture_output=True, text=True, timeout=60)
    if prs.returncode == 0 and prs.stdout.strip() not in ("", "[]"):
        raise ValueError(f"branch {branch!r} already had a PR; reusing its name recreates an orphan ref")
    project = project or project_identity(root)
    if checkout is not None:
        checkout = checkout.resolve()
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=checkout if checkout.is_dir() else root,
                             capture_output=True, text=True, timeout=60)
        if not checkout.is_dir() or top.returncode != 0 or Path(top.stdout.strip()).resolve() != checkout:
            raise ValueError(f"{checkout} is not a Git checkout")
        if project_identity(checkout) != project_identity(root):
            raise ValueError(f"{checkout} is a clone of another project")
        if subprocess.run(["git", "rev-parse", "-q", "--verify", f"refs/heads/{branch}"], cwd=checkout,
                          capture_output=True, timeout=60).returncode == 0:
            raise ValueError(f"branch {branch!r} already exists in {checkout}; start new work on a new branch")
        worktree = checkout
    else:
        worktree = (worktree_root or default_worktree_root()) / f"{root.name}-{branch.replace('/', '-')}"
        if worktree.exists():
            raise ValueError(f"{worktree} already exists")
    mission = ledger.create_mission(title)
    ledger.acquire_claims(project_root=project, mission_id=mission, holder=branch,
                          targets=[("branch", branch)] + [("path", path) for path in paths])
    created = (subprocess.CompletedProcess([], 0, "", "") if checkout is not None
               else git("worktree", "add", "-q", "-b", branch, str(worktree), base))
    if created.returncode != 0:
        ledger.release_claims(mission_id=mission, project_root=project, reason="failed",
                              released_by="harness-agent", holder=branch)
        raise ValueError(f"git worktree add failed: {created.stderr.strip()[:300]}")
    ledger.record_mission_event(
        job_id=None, source_sha=None, mission_id=mission, event_id=uuid.uuid4().hex,
        event_type="checkpoint",
        checkpoint={"stage": "opened", "status": "running", "branch": branch, "worktree": str(worktree)})
    return {"mission_id": mission, "branch": branch, "worktree": str(worktree),
            "claims": [branch, *paths]}
