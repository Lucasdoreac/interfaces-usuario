"""PARADIGMA: relatório só-leitura — cada missão aberta sai com a transição que a prova permite, ou como cartão.

The dry-run step (M1) of the mission reconciler: it reads every registered ledger
read-only, folds each mission, and asks GitHub about the branches the mission claimed.
A transition is proposed only with a named proof; everything else is a card for the
owner, and an unreadable source is ``not_measured``, never an inference.

Items are keyed by ``(ledger path, mission id)``. Mission ids are per ledger (the same id
names different missions in the SOBER and harness ledgers), and no ledger identity has
been decided yet, so the key is marked provisional.

Proposals today:

- ``release_merged``: the mission is the branch's owner (``mission_lifecycle.owners``) and
  exactly one PR from that branch is MERGED. Proof: ledger, mission, branch, PR, state,
  merge and head SHAs. The release itself goes through the existing ``merged`` reason.

A CLOSED PR stays a card until a release authority for it exists.

A parked mission is an item too, never hidden: ``kind: parked`` with its reason, its
``resume_on`` condition and ``due`` (did the condition fire: the PR left OPEN, the claim
was released, the date arrived). A park recorded without a condition is the card
``parked_without_resume_condition``: nothing would ever resume it.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Callable

from . import mission_lifecycle
from .ledger import mission_branches
from .worktrees import NotMeasured

GhRunner = Callable[[list[str], Path], str]
PR_FIELDS = "number,state,headRefName,headRefOid,mergeCommit,url"


def _gh(args: list[str], cwd: Path) -> str:
    from .branch_gc import _gh as run

    return run(args, cwd)


def _read(ledger: Path) -> tuple[list[int], list[dict], dict[int, list[dict]]]:
    """Mission ids, every claim (held or released) and each mission's events, read-only."""
    conn = sqlite3.connect(f"file:{ledger}?mode=ro", uri=True)
    try:
        conn.row_factory = sqlite3.Row
        missions = [int(row[0]) for row in conn.execute("SELECT mission_id FROM update_missions ORDER BY mission_id")]
        claims = [dict(row) for row in conn.execute(
            "SELECT claim_id,kind,target,mission_id,holder,project_root,released_at FROM update_claims")]
        events: dict[int, list[dict]] = {}
        for mission, kind, raw, created in conn.execute(
                "SELECT mission_id,event_type,event_json,created_at FROM update_mission_events "
                "ORDER BY created_at,event_id"):
            event = json.loads(raw)
            event["event_type"], event["created_at"] = kind, created
            events.setdefault(int(mission), []).append(event)
    finally:
        conn.close()
    return missions, claims, events


def _last(events: list[dict]) -> dict[str, Any]:
    if not events:
        return {}
    event = events[-1]
    checkpoint = event.get("checkpoint") or {}
    return {"event_type": event.get("event_type"), "at": event.get("created_at"),
            "stage": checkpoint.get("stage"), "next_step": checkpoint.get("next_step")}


def _pr_rows(events: list[dict]) -> list[dict]:
    """Latest blocked/waiting row per PR, as the orphan PR sweeper records them."""
    rows: dict[int, dict] = {}
    for event in events:
        checkpoint = event.get("checkpoint") or {}
        if event.get("event_type") in {"blocked", "waiting"} and isinstance(checkpoint.get("pr_number"), int):
            rows[checkpoint["pr_number"]] = {"pr": checkpoint["pr_number"], "stage": checkpoint.get("stage"),
                                             "next_step": checkpoint.get("next_step")}
    return [rows[number] for number in sorted(rows)]


def _assess(mission: int, ledger: Path, claims: list[dict], roots: dict[str, Path],
            by_branch: dict[tuple[str, str], int], gh: GhRunner) -> dict[str, Any]:
    own = [c for c in claims if int(c["mission_id"]) == mission]
    if not own:
        return {"kind": "card", "reason": "no_claims"}
    project = own[0]["project_root"]
    branches = sorted((project, branch) for branch in mission_branches(own, mission))
    if not branches:
        return {"kind": "card", "reason": "no_branch_claim"}
    by_claim = any(c["kind"] == "branch" for c in own)
    others = {int(c["mission_id"]) for c in claims if int(c["mission_id"]) != mission
              and c["project_root"] == project and c["holder"] in {b for _, b in branches}}
    if (by_claim and any(by_branch.get(item) != mission for item in branches)) or (not by_claim and others):
        return {"kind": "card", "reason": "branch_owner_ambiguous",
                "branches": [branch for _, branch in branches]}
    prs: list[dict] = []
    for project, branch in branches:
        root = roots.get(project)
        if root is None:
            return {"kind": "not_measured", "reason": f"project {project} is not in the ledger registry"}
        try:
            found = json.loads(_gh_list(gh, root, branch))
        except (NotMeasured, ValueError) as exc:
            return {"kind": "not_measured", "reason": str(exc)}
        prs += [{**pr, "branch": branch} for pr in found if pr.get("headRefName") == branch]
    merged = [pr for pr in prs if pr.get("state") == "MERGED"]
    if len(merged) == 1 and (merged[0].get("mergeCommit") or {}).get("oid"):
        pr = merged[0]
        return {"kind": "proposal", "transition": "release_merged",
                "proof": {"ledger": str(ledger), "mission": mission, "branch": pr["branch"], "pr": pr["number"],
                          "state": "MERGED", "merge_sha": pr["mergeCommit"]["oid"],
                          "head_sha": pr.get("headRefOid"), "url": pr.get("url")}}
    numbers = sorted(pr["number"] for pr in prs)
    if merged:
        return {"kind": "card", "reason": "several_merged_prs", "prs": numbers}
    if any(pr.get("state") == "OPEN" for pr in prs):
        return {"kind": "card", "reason": "pr_open", "prs": numbers}
    if prs:
        return {"kind": "card", "reason": "pr_closed_no_release_authority", "prs": numbers}
    return {"kind": "card", "reason": "no_pr", "branches": [branch for _, branch in branches]}


def _parked(state: mission_lifecycle.MissionState, mission: int, claims: list[dict], roots: dict[str, Path],
            gh: GhRunner, today: datetime.date) -> dict[str, Any]:
    """Whether the park's resume condition fired, measured from its own source."""
    if not state.resume_on or not state.park_reason:
        return {"kind": "card", "reason": "parked_without_resume_condition"}
    item = {"kind": "parked", "reason": state.park_reason, "resume_on": state.resume_on}
    source, _, value = state.resume_on.partition(":")
    if source == "date":
        return {**item, "due": today >= datetime.date.fromisoformat(value)}
    if source == "claim":
        claim = next((c for c in claims if c.get("claim_id") == int(value)), None)
        if claim is None:
            return {"kind": "not_measured", "reason": f"claim {value} is not in this ledger"}
        return {**item, "due": claim["released_at"] is not None}
    own = [c for c in claims if int(c["mission_id"]) == mission]
    root = roots.get(own[0]["project_root"]) if own else None
    if root is None:
        return {"kind": "not_measured", "reason": "the mission's project is not in the ledger registry"}
    try:
        observed = json.loads(gh(["pr", "view", value, "--json", "state"], root)).get("state")
    except (NotMeasured, ValueError) as exc:
        return {"kind": "not_measured", "reason": str(exc)}
    return {**item, "due": observed != "OPEN", "observed": observed}


def _failed_and_released(mission: int, claims: list[dict], events: dict[int, list[dict]]) -> bool:
    """A run that failed and released every claim it held: nothing is left to decide or reclaim."""
    own = [c for c in claims if int(c["mission_id"]) == mission]
    releases = [e for e in events.get(mission, []) if e.get("event_type") == "claim_released"]
    return bool(own) and all(c["released_at"] is not None for c in own) and bool(releases) and \
        (releases[-1].get("checkpoint") or {}).get("release_reason") == "failed"


def _gh_list(gh: GhRunner, root: Path, branch: str) -> str:
    return gh(["pr", "list", "--state", "all", "--head", branch, "--json", PR_FIELDS], root)


def report(projects: list[tuple[str, Path, Path]], *, gh: GhRunner = _gh,
           today: datetime.date | None = None) -> dict[str, Any]:
    """One item per open or parked mission of each distinct ledger; nothing is written."""
    today = today or datetime.date.today()
    roots = {identity: root for identity, root, _ in projects}
    items: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for _identity, _root, ledger in projects:
        if ledger in seen or not ledger.is_file():
            continue
        seen.add(ledger)
        missions, claims, events = _read(ledger)
        by_branch: dict[tuple[str, str], int] = {}
        for project in {c["project_root"] for c in claims}:
            owned, _ = mission_lifecycle.owners(ledger, [c for c in claims if c["project_root"] == project])
            by_branch.update({(project, branch): mission for branch, mission in owned.items()})
        for mission in missions:
            state = mission_lifecycle.fold(mission, events.get(mission, []))
            if state.parked:
                if state.state == "collected":
                    continue
                verdict = _parked(state, mission, claims, roots, gh, today)
            elif state.state != "active" or _failed_and_released(mission, claims, events):
                continue
            else:
                verdict = _assess(mission, ledger, claims, roots, by_branch, gh)
            item = {"key": {"ledger": str(ledger), "mission": mission, "provisional": True},
                    **verdict, "last": _last(events.get(mission, []))}
            if rows := _pr_rows(events.get(mission, [])):
                item["pr_rows"] = rows
            items.append(item)
    counts: dict[str, int] = {}
    for item in items:
        counts[item["kind"]] = counts.get(item["kind"], 0) + 1
    return {"dry_run": True, "counts": counts, "items": items}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="harness-reconcile", description=__doc__.splitlines()[0])
    parser.add_argument("--registry", type=Path,
                        default=Path(os.environ.get("HARNESS_LEDGER_REGISTRY")
                                     or Path.home() / ".local/state/harness/ledgers.json"))
    args = parser.parse_args(argv)
    bindings = json.loads(args.registry.read_text(encoding="utf-8")) if args.registry.is_file() else {}
    projects = [(identity, Path(path).parent.parent, Path(path)) for identity, path in sorted(bindings.items())]
    print(json.dumps(report(projects), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
