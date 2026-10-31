"""PARADIGMA: find open PRs that no mission owns any more, and say what state each is in.

An open PR is claimed when the project's canonical ledger holds an active
``branch`` claim on its head branch: some mission took it and has not released
it. Every other open PR is orphaned. Each orphan is classified against its base
branch (``origin/<baseRefName>``):

    draft_snapshot   a draft whose title or branch marks it as a snapshot or
                     preservation PR, kept on purpose and not meant to merge (the
                     body is not read: prose like "preserves ordering" is no mark)
    absorbed         the reverse of merge-base..head applies cleanly to the base:
                     every change is already there
    applies_cleanly  a three-way merge with the base has no conflict
    conflicting      the merge conflicts; the files are named
    not_measured     the head commit or the merge base could not be read

The report states each PR's age and idle time. With ``--record`` one mission
event per orphan goes to the ledger, under one sweeper mission per ledger; the
event ID is derived from the PR, its head and its state, so a rerun with
nothing changed appends nothing. The sweeper only reads PRs: it never closes,
merges, rebases or comments on one. Acting on a PR is the owner's decision, or
the work of a mission that claims it.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import tempfile
import time

from .worktrees import NotMeasured, _chunks, _git, _names, list_worktrees, open_prs

PR_FIELDS = ("number,title,headRefName,headRefOid,baseRefName,url,isDraft,"
             "createdAt,updatedAt,author")
SNAPSHOT_MARKER = re.compile(r"snapshot|preserv", re.IGNORECASE)
MISSION_TITLE = "Orphaned PR sweeper"
STATES = ("draft_snapshot", "absorbed", "applies_cleanly", "conflicting", "not_measured")
SHOWN_FILES = 6
EVENT_FILES = 20  # the ledger accepts at most 20 paths per checkpoint


def _git_status(root: Path, *args: str, stdin: bytes | None = None,
                env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=root, input=stdin, capture_output=True, check=False,
                          env={**os.environ, **(env or {})})


def _schema_version(ledger_path: Path) -> int:
    try:
        conn = sqlite3.connect(f"file:{ledger_path}?mode=ro", uri=True)
        try:
            return conn.execute("PRAGMA user_version").fetchone()[0]
        finally:
            conn.close()
    except sqlite3.Error as exc:
        raise NotMeasured(f"ledger {ledger_path} is unreadable: {exc}") from exc


def claimed_branches(ledger_path: Path, project: str) -> dict[str, int]:
    """Active branch claims of the project: head branch -> mission.

    The ledger is opened only when its schema is current; opening an older one
    would migrate another project's production record in place.
    """
    from .ledger import SCHEMA_VERSION, Ledger

    if not ledger_path.is_file():
        raise NotMeasured(f"ledger {ledger_path} does not exist; claims cannot be read")
    version = _schema_version(ledger_path)
    if version < SCHEMA_VERSION:
        raise NotMeasured(f"ledger {ledger_path} has schema v{version} < v{SCHEMA_VERSION}; not migrated")
    return {claim["target"]: claim["mission_id"]
            for claim in Ledger(ledger_path).claims(project_root=project) if claim["kind"] == "branch"}


def _head_commit(root: Path, pr: dict, *, fetch: bool) -> str | None:
    """The PR head SHA when its commit is in the local object store.

    A missing head is fetched from ``refs/pull/<n>/head`` without writing any
    ref or FETCH_HEAD, so the checkout's branches and remotes stay as they were.
    """
    sha = pr.get("headRefOid") or ""
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        return None
    present = _git_status(root, "cat-file", "-e", f"{sha}^{{commit}}").returncode == 0
    if not present and fetch:
        _git_status(root, "fetch", "--quiet", "--no-tags", "--no-write-fetch-head", "origin",
                    f"refs/pull/{pr['number']}/head")
        present = _git_status(root, "cat-file", "-e", f"{sha}^{{commit}}").returncode == 0
    return sha if present else None


def _reverse_applies(root: Path, base: str, merge_base: str, head: str) -> bool:
    """The PR's own diff, reversed, applies cleanly to the base tree (index only)."""
    diff = _git_status(root, "diff", "--binary", "--full-index", merge_base, head)
    if diff.returncode != 0:
        raise NotMeasured(f"git diff {merge_base[:12]}..{head[:12]} failed")
    if not diff.stdout.strip():
        return True
    with tempfile.TemporaryDirectory(prefix="harness-orphan-") as scratch:
        env = {"GIT_INDEX_FILE": str(Path(scratch) / "index")}
        if _git_status(root, "read-tree", base, env=env).returncode != 0:
            raise NotMeasured(f"git read-tree {base} failed")
        return _git_status(root, "apply", "--cached", "--reverse", "--check", "--binary", "-",
                           stdin=diff.stdout, env=env).returncode == 0


def git_state(root: Path, base: str, head: str) -> dict:
    """Classify one head against the base: absorbed, applies cleanly, or conflicting."""
    merge_base = _git_status(root, "merge-base", base, head)
    if merge_base.returncode != 0:
        raise NotMeasured(f"no merge base between {base} and {head[:12]}")
    mb = merge_base.stdout.decode().strip()
    changed = sorted(_names(_git(root, "diff", "--name-only", "-z", mb, head)))
    remaining: set[str] = set()
    for chunk in _chunks(changed):
        remaining |= _names(_git(root, "--literal-pathspecs", "diff", "--name-only", "-z",
                                 base, head, "--", *chunk))
    facts = {"merge_base": mb, "changed_files": len(changed),
             "files_already_in_base": len(set(changed) - remaining), "conflicts": []}
    if _reverse_applies(root, base, mb, head):
        return {"git_state": "absorbed", **facts}
    merged = _git_status(root, "merge-tree", "--write-tree", "--name-only", "--no-messages", "-z",
                         base, head)
    if merged.returncode == 0:
        return {"git_state": "applies_cleanly", **facts}
    if merged.returncode != 1:
        raise NotMeasured(f"git merge-tree failed: {merged.stderr.decode(errors='replace')[:200]}")
    names = [name for name in merged.stdout.decode(errors="replace").split("\0")[1:] if name]
    facts["conflicts"] = list(dict.fromkeys(names))
    return {"git_state": "conflicting", **facts}


def _days(stamp: str | None, now: float) -> float | None:
    if not stamp:
        return None
    moment = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    return round((now - moment.timestamp()) / 86400, 1)


def classify(root: Path, pr: dict, *, fetch: bool, now: float) -> dict:
    entry = {
        "pr": pr["number"], "title": pr.get("title"), "url": pr.get("url"),
        "branch": pr.get("headRefName"), "head_sha": pr.get("headRefOid"),
        "base": f"origin/{pr.get('baseRefName') or 'main'}", "draft": bool(pr.get("isDraft")),
        "author": (pr.get("author") or {}).get("login"),
        "age_days": _days(pr.get("createdAt"), now), "idle_days": _days(pr.get("updatedAt"), now),
    }
    marked = f"{pr.get('title') or ''} {pr.get('headRefName') or ''}"
    snapshot = entry["draft"] and bool(SNAPSHOT_MARKER.search(marked))
    head = _head_commit(root, pr, fetch=fetch)
    try:
        if head is None:
            raise NotMeasured(f"head {str(entry['head_sha'])[:12]} is not available locally")
        entry |= git_state(root, entry["base"], head)
    except NotMeasured as exc:
        entry |= {"git_state": "not_measured", "reason": str(exc), "conflicts": []}
    entry["state"] = "draft_snapshot" if snapshot else entry["git_state"]
    return entry


def sweep(root: Path, project: str, ledger_path: Path, *, fetch: bool = True,
          now: float | None = None) -> dict:
    """Report every open PR of the project as claimed or orphaned (with its state)."""
    stamp = time.time() if now is None else now
    claims = claimed_branches(ledger_path, project)
    if fetch:
        _git(root, "fetch", "--quiet", "--prune", "origin")
    prs = open_prs(root, PR_FIELDS)
    worktrees = {entry["branch"].removeprefix("refs/heads/"): entry["worktree"]
                 for entry in list_worktrees(root) if entry.get("branch") and entry.get("worktree")}
    claimed, orphaned = [], []
    for pr in sorted(prs, key=lambda item: item["number"]):
        branch = pr.get("headRefName")
        if branch in claims:
            claimed.append({"pr": pr["number"], "branch": branch, "mission": claims[branch]})
            continue
        entry = classify(root, pr, fetch=fetch, now=stamp)
        entry["worktree"] = worktrees.get(branch)
        orphaned.append(entry)
    return {
        "project": project, "repo": str(root), "ledger": str(ledger_path),
        "measured_at": datetime.fromtimestamp(stamp, timezone.utc).isoformat(timespec="seconds"),
        "open_prs": len(prs), "claimed": claimed, "orphaned": orphaned,
        "counts": {state: sum(1 for e in orphaned if e["state"] == state) for state in STATES},
    }


def _sweeper_mission(ledger) -> int:
    """The ledger's one sweeper mission, created on the first recorded run."""
    with ledger._session() as db:
        row = db.execute("SELECT min(mission_id) FROM update_missions WHERE title=?",
                         (MISSION_TITLE,)).fetchone()
    return int(row[0]) if row[0] is not None else ledger.create_mission(MISSION_TITLE)


def record(ledger_path: Path, report: dict) -> dict:
    """One mission event per orphaned PR under the sweeper mission; a replay appends nothing."""
    from .ledger import Ledger, _derived_event_id

    ledger = Ledger(ledger_path)
    mission = _sweeper_mission(ledger)
    appended = 0
    for entry in report["orphaned"]:
        files = (entry.get("conflicts") or [])[:EVENT_FILES]
        checkpoint = {"stage": f"orphan_{entry['state']}", "status": "waiting", "next_step": "wait",
                      "pr_number": entry["pr"], "branch": entry["branch"]}
        if entry.get("head_sha"):
            checkpoint["head_sha"] = entry["head_sha"]
        if files:
            checkpoint["files"] = files
        arguments = dict(job_id=None, source_sha=None, mission_id=mission, event_type="blocked",
                         event_id=_derived_event_id("orphan-pr", report["project"], entry["pr"],
                                                    entry.get("head_sha"), entry["state"], *sorted(files)))
        try:
            appended += ledger.record_mission_event(**arguments, checkpoint=checkpoint)
        except ValueError:  # a branch name the journal refuses: keep the PR, drop the name
            checkpoint.pop("branch")
            appended += ledger.record_mission_event(**arguments, checkpoint=checkpoint)
    return {"mission": mission, "events_appended": appended}


def summary(report: dict) -> str:
    counts = ", ".join(f"{n} {state}" for state, n in report["counts"].items() if n)
    lines = [f"{report['project']}: {report['open_prs']} open PR(s), {len(report['claimed'])} claimed, "
             f"{len(report['orphaned'])} orphaned" + (f" ({counts})" if counts else "")]
    for entry in report["orphaned"]:
        text = (f"  #{entry['pr']} {entry['state']}: {entry['age_days']}d old, idle {entry['idle_days']}d, "
                f"{entry['branch']}")
        if entry["state"] != entry["git_state"]:
            text += f" [git: {entry['git_state']}]"
        if entry.get("changed_files"):
            text += f"; {entry['files_already_in_base']}/{entry['changed_files']} files already in base"
        if entry["conflicts"]:
            shown = entry["conflicts"][:SHOWN_FILES]
            more = len(entry["conflicts"]) - len(shown)
            text += f"; conflicts: {', '.join(shown)}" + (f" (+{more})" if more else "")
        if entry.get("reason"):
            text += f"; {entry['reason']}"
        lines.append(text)
    return "\n".join(lines)


def state_dir() -> Path:
    return Path(os.environ.get("HARNESS_ORPHAN_STATE")
                or Path.home() / ".local" / "state" / "harness" / "orphan-prs")


def _registered_target(identity: str, value: str) -> tuple[Path, Path]:
    """Canonical checkout and ledger of one registry binding.

    The registry stores a ledger, not a checkout: the checkout is inferred only
    from an absolute ledger whose real location is a Git toplevel's
    `.sober/update-vanguard.sqlite3` and whose project identity matches.
    """
    from .agent import default_ledger_path, project_identity

    hint = "pass --repo PATH (with --ledger PATH for an external ledger)"
    ledger = Path(value).expanduser()
    if not ledger.is_absolute():
        raise NotMeasured(f"registry ledger {value!r} is relative; {hint}")
    ledger = ledger.resolve()
    root = ledger.parent.parent
    if default_ledger_path(root) != ledger or not root.is_dir():
        raise NotMeasured(f"no checkout can be derived from ledger {ledger}; {hint}")
    try:
        top = Path(_git(root, "rev-parse", "--show-toplevel").strip()).resolve()
    except NotMeasured as exc:
        raise NotMeasured(f"{exc}; {hint}") from exc
    if top != root or project_identity(root) != identity:
        raise NotMeasured(f"checkout {root} is not the registered project {identity}; {hint}")
    return root, ledger


def main(argv: list[str] | None = None) -> int:
    from .agent import _read_registry, project_identity, resolve_ledger
    from .vulnerabilities import _slug

    parser = argparse.ArgumentParser(prog="harness-orphan-prs", description=__doc__.splitlines()[0])
    parser.add_argument("--registry", type=Path,
                        default=Path(os.environ.get("HARNESS_LEDGER_REGISTRY")
                                     or Path.home() / ".local/state/harness/ledgers.json"),
                        help="projects to sweep (default: the harness ledger registry)")
    parser.add_argument("--repo", type=Path, action="append",
                        help="sweep only this repository (repeatable); its ledger is resolved as usual")
    parser.add_argument("--ledger", type=Path, help="with one --repo: the claims ledger to read")
    parser.add_argument("--no-fetch", action="store_true",
                        help="do not fetch the base or missing PR heads from origin")
    parser.add_argument("--record", action="store_true",
                        help="append one mission event per orphaned PR and keep the JSON report "
                             "under the harness state directory")
    parser.add_argument("--json", action="store_true", help="print the JSON report instead of the summary")
    args = parser.parse_args(argv)
    if args.ledger is not None and len(args.repo or []) != 1:
        parser.error("--ledger goes with exactly one --repo")
    bindings = _read_registry(args.registry) if not args.repo else {}
    if args.repo:
        targets = []
        for repo in args.repo:
            root = Path(_git(repo.resolve(), "rev-parse", "--show-toplevel").strip())
            targets.append((project_identity(root), root, resolve_ledger(args.ledger, root)))
    else:
        targets = [(identity, None, path) for identity, path in sorted(bindings.items())]
    status, reports = 0, []
    for identity, root, ledger_path in targets:
        try:
            if root is None:
                root, ledger_path = _registered_target(identity, ledger_path)
            report = sweep(root, identity, ledger_path, fetch=not args.no_fetch)
        except NotMeasured as exc:
            print(json.dumps({"project": identity, "not_measured": str(exc)}), file=sys.stderr)
            status = 2
            continue
        if args.record:
            report["recorded"] = record(ledger_path, report)
            from . import mission_lifecycle
            from .ledger import Ledger

            # Time only raises a signal here: an idle mission becomes `stalled`, never collected.
            report["stalled_missions"] = mission_lifecycle.mark_stalled(Ledger(ledger_path), idle_days=7)
            path = state_dir() / f"{_slug(identity)}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
            os.replace(tmp, path)
        reports.append(report)
        if not args.json:
            print(summary(report))
    if args.json:
        print(json.dumps(reports, indent=2))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
