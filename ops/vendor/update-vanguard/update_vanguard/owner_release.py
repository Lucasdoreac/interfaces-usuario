"""PARADIGMA: liberação do dono com prova — o que nenhum titular nem portão pode liberar sai só com o fato medido gravado no claim.

Two releases have no holder or gate to make them:

- ``orphan_mission``: claims whose mission id this ledger does not hold (written before
  the claim commands refused them). Mission ids are per ledger, so the same id in another
  ledger is another mission; nothing here can release them as that mission.
- ``pr_closed``: claims of a mission whose PR was closed without merge.
- ``merged_pr`` (no release): a mission with no claims and no branch whose PR merged.
  Nothing in the ledger links it to the PR, so the owner names it and the link is
  recorded as ``owner_statement``; the proof is the PR MERGED with its merge commit in the
  base, and no other mission recording that PR as merged.

The owner runs them (``harness-agent claims release-orphan|release-closed``). Both
measure the same proof before writing: no open PR on the holder branch, and every
worktree on that branch or recorded for the mission (a detached one at the PR head
included) clean and without a live process. ``orphan_mission`` also needs
the worktree merged; ``pr_closed`` needs the PR CLOSED, from the mission's branch, at the
branch's current tip (nothing pushed after the close). The proof is recorded with the
release. An unreadable source refuses; it is never read as "nothing there".
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from . import mission_lifecycle
from .agent import project_identity
from .ledger import ClaimAuthorityError, Ledger
from .worktree_gc import _inside, live_cwds
from .worktrees import NotMeasured, _git, list_worktrees, local_changes, pending_files

GhRunner = Callable[[list[str], Path], str]


def _gh(args: list[str], cwd: Path) -> str:
    from .branch_gc import _gh as run

    return run(args, cwd)


def _open_prs(gh: GhRunner, root: Path, branch: str) -> list[int]:
    found = json.loads(gh(["pr", "list", "--state", "open", "--head", branch, "--json", "number,headRefName"], root))
    return sorted(pr["number"] for pr in found if pr.get("headRefName") == branch)


def _recorded(ledger: Ledger, mission: int) -> set[str]:
    """Worktree paths the mission's journal records as its own (e.g. a detached one at a PR head)."""
    _, by_worktree = mission_lifecycle.owners(ledger.path, None)
    return {path for path, owner in by_worktree.items() if owner == mission}


def _measure(path: Path, processes: dict[int, list[str]], *, base: str, require_merged: bool) -> dict[str, Any]:
    tracked, untracked = local_changes(path)
    untracked = {name for name in untracked if Path(name).parts[0] != ".venv"}
    live = sorted(pid for pid, links in processes.items() if any(_inside(link, path) for link in links))
    if live:
        raise ClaimAuthorityError(f"live process {live} inside {path}")
    if tracked or untracked:
        raise ClaimAuthorityError(f"{path} has local changes")
    merged = not pending_files(path, base, tracked, untracked)
    if require_merged and not merged:
        raise ClaimAuthorityError(f"{path} is not merged into {base}")
    return {"worktree": str(path), "head": _git(path, "rev-parse", "HEAD").strip(),
            "clean": True, "merged": merged, "live_pids": []}


def _worktrees(root: Path, branch: str, *, base: str, proc: Path, require_merged: bool,
               recorded: set[str] = frozenset()) -> list[dict[str, Any]]:
    """Every checkout of the mission, measured; refuses dirty, live or (if required) unmerged ones.

    That is every worktree on ``branch`` and every path the mission's journal records, whether
    or not git lists it as a worktree: a task runner's clone (``mission open --checkout``) has its
    own .git. A recorded path that no longer exists is reported as missing, never measured clean.
    """
    processes = live_cwds(proc)
    measured, seen = [], set()
    for entry in list_worktrees(root)[1:]:
        on_branch = entry.get("branch", "").removeprefix("refs/heads/") == branch
        if not (on_branch or entry.get("worktree") in recorded) or "prunable" in entry:
            continue
        path = Path(entry["worktree"])
        seen.add(str(path.resolve()))
        measured.append(_measure(path, processes, base=base, require_merged=require_merged))
    for text in sorted(recorded):
        path = Path(text)
        if str(path.resolve()) in seen:
            continue
        if not path.exists():
            measured.append({"worktree": text, "missing": True})
            continue
        measured.append(_measure(path, processes, base=base, require_merged=require_merged))
    return measured


def _proof(root: Path, branch: str, *, gh: GhRunner, base: str, proc: Path, require_merged: bool,
           recorded: set[str] = frozenset()) -> dict:
    open_prs = _open_prs(gh, root, branch)
    if open_prs:
        raise ClaimAuthorityError(f"open PR {open_prs} on {branch}")
    return {"branch": branch, "open_prs": [],
            "worktrees": _worktrees(root, branch, base=base, proc=proc, require_merged=require_merged,
                                    recorded=recorded)}


def _ids(result: dict[str, Any]) -> list[int]:
    return sorted(item["claim_id"] if isinstance(item, dict) else item for item in result["released"])


def release_orphan(ledger: Ledger, root: Path, claim_ids: list[int], *, by: str, gh: GhRunner | None = None,
                   base: str = "origin/main", proc: Path = Path("/proc")) -> dict[str, Any]:
    """Release active claims of one mission id this ledger does not hold."""
    gh = gh or _gh
    project = project_identity(root)
    wanted = set(claim_ids)
    rows = [c for c in ledger.claims(project_root=project) if c["claim_id"] in wanted]
    if not wanted or {c["claim_id"] for c in rows} != wanted:
        raise ClaimAuthorityError(f"claims {sorted(wanted - {c['claim_id'] for c in rows})} are not active "
                                  f"claims of {project}")
    missions = {c["mission_id"] for c in rows}
    holders = {c["holder"] for c in rows}
    if len(missions) != 1 or len(holders) != 1:
        raise ClaimAuthorityError("orphan claims are released one mission and holder at a time")
    mission, holder = missions.pop(), holders.pop()
    branches = {c["target"] for c in rows if c["kind"] == "branch"} or {holder}
    # The ledger checks, in the release transaction, that no row for this mission exists.
    proof = {"ledger": str(ledger.path), "mission": mission, "mission_row": False, "claim_ids": sorted(wanted)}
    for branch in sorted(branches):
        proof.setdefault("branches", []).append(
            _proof(root, branch, gh=gh, base=base, proc=proc, require_merged=True,
                   recorded=_recorded(ledger, mission)))
    proof["open_prs"] = []
    proof["worktrees"] = [w for item in proof["branches"] for w in item["worktrees"]]
    result = ledger.release_claims(mission_id=mission, reason="orphan_mission", released_by=by,
                                   project_root=project, targets=[(c["kind"], c["target"]) for c in rows],
                                   owner_release=True, proof=proof)
    return {"mission_id": mission, "released": _ids(result), "proof": proof}


def release_closed(ledger: Ledger, root: Path, mission: int, pr_number: int, *, by: str, gh: GhRunner | None = None,
                   base: str = "origin/main", proc: Path = Path("/proc")) -> dict[str, Any]:
    """Close a mission whose PR was closed unmerged, at the head it closed at, and release its claims."""
    gh = gh or _gh
    project = project_identity(root)
    branches = sorted({c["target"] for c in ledger.claims(project_root=project, mission_id=mission,
                                                          active_only=False) if c["kind"] == "branch"})
    pr = json.loads(gh(["pr", "view", str(pr_number), "--json", "number,state,headRefName,headRefOid"], root))
    if pr.get("state") != "CLOSED" or pr.get("headRefName") not in branches:
        raise ClaimAuthorityError(f"PR #{pr_number} is not a closed PR of the mission's branch {branches}")
    branch, head = pr["headRefName"], pr.get("headRefOid")
    remote = _git(root, "ls-remote", "origin", f"refs/heads/{branch}").split()
    tip = remote[0] if remote else _git(root, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}").strip()
    if not tip:
        raise NotMeasured(f"no tip for {branch} on the remote or locally")
    if tip != head:
        raise ClaimAuthorityError(f"PR #{pr_number} closed at {head}, but the branch tip is {tip}")
    proof = {"ledger": str(ledger.path), "mission": mission, "pr_number": pr_number, "state": "CLOSED",
             "head_sha": head, "branch_tip": tip,
             **_proof(root, branch, gh=gh, base=base, proc=proc, require_merged=False,
                      recorded=_recorded(ledger, mission))}
    if mission_lifecycle.state(ledger, mission).state == "active":
        mission_lifecycle.record(ledger, mission, "pr_closed", pr_number=pr_number)
    result = ledger.release_claims(mission_id=mission, reason="pr_closed", released_by=by,
                                   project_root=project, owner_release=True, proof=proof)
    return {"mission_id": mission, "released": _ids(result), "proof": proof}


def _missions_recording_merge(ledger: Ledger, pr_number: int) -> set[int]:
    """Missions whose journal records ``pr_number`` as merged (merge release or merged_pr)."""
    import sqlite3

    conn = sqlite3.connect(f"file:{ledger.path}?mode=ro", uri=True)
    try:
        rows = conn.execute("SELECT mission_id,event_json FROM update_mission_events "
                            "WHERE event_type IN ('checkpoint','claim_released')").fetchall()
    finally:
        conn.close()
    found = set()
    for mission, raw in rows:
        checkpoint = json.loads(raw).get("checkpoint") or {}
        if checkpoint.get("pr_number") == pr_number and (
                checkpoint.get("stage") == "merged_pr" or checkpoint.get("release_reason") == "merged"):
            found.add(int(mission))
    return found


def record_merged(ledger: Ledger, root: Path, mission: int, pr_number: int, *, by: str,
                  gh: GhRunner | None = None, base: str = "origin/main") -> dict[str, Any]:
    """Record ``merged`` for a mission that holds no claims, on the owner's PR number and its proof."""
    gh = gh or _gh
    current = mission_lifecycle.state(ledger, mission)
    if current.state != "active" or current.parked:
        raise mission_lifecycle.InvalidTransition(f"mission {mission} is {current.state}; merged_pr is not allowed")
    active = ledger.claims(mission_id=mission)
    if active:
        raise ClaimAuthorityError(f"mission {mission} holds active claims; its merge releases them "
                                  "(harness-agent release --merged-pr)")
    events = ledger.mission_events(mission)
    if any((e.get("checkpoint") or {}).get("stage") == "opened" for e in events) or any(
            c["kind"] == "branch" for c in ledger.claims(mission_id=mission, active_only=False)):
        raise ClaimAuthorityError(f"mission {mission} has a branch; it closes through its branch "
                                  "(merge gate, release --merged-pr, branch-gc), not on the owner's word")
    for other in _missions_recording_merge(ledger, pr_number):
        if other != mission:
            raise ClaimAuthorityError(f"mission {other} already records PR #{pr_number} as merged")
    pr = json.loads(gh(["pr", "view", str(pr_number), "--json", "number,state,mergeCommit"], root))
    merge = (pr.get("mergeCommit") or {}).get("oid")
    if pr.get("state") != "MERGED" or not isinstance(merge, str):
        raise ClaimAuthorityError(f"PR #{pr_number} is not merged")
    _git(root, "fetch", "-q", "origin")
    import subprocess

    if subprocess.run(["git", "merge-base", "--is-ancestor", merge, base], cwd=root,
                      capture_output=True).returncode != 0:
        raise ClaimAuthorityError(f"merge commit {merge} of PR #{pr_number} is not in {base}")
    proof = {"ledger": str(ledger.path), "mission": mission, "pr_number": pr_number, "state": "MERGED",
             "merge_sha": merge, "in_base": base, "active_claims": 0}
    # The ledger cannot prove the PR is this mission's: the link is the owner's statement.
    state = mission_lifecycle.record(ledger, mission, "merged_pr", pr_number=pr_number, head_sha=merge,
                                     facts={"link": "owner_statement", "actor": by})
    return {**state.as_dict(), "recorded_by": by, "proof": proof}
