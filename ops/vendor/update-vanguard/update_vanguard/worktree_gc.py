"""PARADIGMA: conservative collector; collect mission worktrees whose work is provably integrated, archiving them first.

A linked worktree (never the canonical checkout, never a locked one) is
eligible only when ALL of these hold:

1. claim: no active claim in the update ledger on its branch or on a path
   inside it; a branch that never had a claim must be merged on the remote main;
2. merged: HEAD is an ancestor of the base (``origin/main``) or every file it
   committed already has the base's content (squash merge);
3. clean: no tracked change and no untracked file except ``.venv``; ignored
   files other than regenerable caches (and a setuptools ``build/`` next to its
   project file) also preserve the worktree;
4. pushed: no commit outside every remote ref;
5. idle: no live process has its cwd or root inside it.

Before removal the collector writes, under a managed archive root, a
``git bundle`` of HEAD, the diff of the branch against the base and of the
working tree, HEAD and status. Then ``git worktree remove`` (never --force) and,
only when merged, ``git branch -D``. Dry-run is the default; ``--apply`` acts.
The ledger is read with a read-only SQLite connection and never migrated.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import time
from typing import Any

from .worktrees import (NotMeasured, _git, list_worktrees, local_changes, merged_pr_heads, open_prs,
                        pending_files, repo_root)

ARCHIVE_MARKER = ".personal-dev-harness-worktree-archive"
REGENERABLE = frozenset({".venv", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"})


def default_archive_root() -> Path:
    return Path.home() / "dev" / "worktrees" / ".archive"


def _git_ok(cwd: Path, *args: str) -> bool:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True).returncode == 0


def ledger_claims(ledger: Path | None, project: str) -> list[dict] | None:
    """Every claim (active and released) of the project; None when no ledger exists."""
    if ledger is None or not ledger.is_file():
        return None
    try:
        conn = sqlite3.connect(f"file:{ledger}?mode=ro", uri=True)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT kind,target,mission_id,holder,released_at FROM update_claims "
                                "WHERE project_root=?", (project,)).fetchall()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        raise NotMeasured(f"ledger {ledger} could not be read: {exc}") from exc
    return [dict(row) for row in rows]


def _live_cwds_lsof() -> dict[int, list[str]]:
    """cwd and root of the caller's processes where there is no ``/proc`` (macOS).

    ``lsof`` runs with the caller's process visibility; the managed worktree root must be controlled
    by that caller. If the process list or its field protocol cannot be measured completely, the
    collector refuses: an unmeasured "idle" is never treated as idle.
    """
    try:
        # cwd="/": lsof inherits the caller's cwd and lists itself; run from inside a worktree, the
        # probe made that worktree look in use (SOBER #744 kept its own worktree, 2026-10-30).
        result = subprocess.run(["lsof", "-nP", "-d", "cwd,rtd", "-F0pfn"], cwd="/", capture_output=True,
                                text=True, timeout=60, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        raise NotMeasured(f"live working directories could not be listed with lsof: {exc}") from exc
    if result.returncode != 0:
        raise NotMeasured(
            f"live working directories could not be listed completely with lsof "
            f"(exit {result.returncode})"
        )
    if not result.stdout.strip():
        raise NotMeasured("lsof listed no working directories; liveness could not be measured")
    found: dict[int, list[str]] = {}
    pid: int | None = None
    expect_name = False
    # `-F0` makes paths containing newlines unambiguous. lsof prefixes file
    # records with a newline; only that one protocol separator is accepted.
    fields = result.stdout.split("\0")
    if fields and fields[-1] == "\n":  # lsof's terminal record separator
        fields.pop()
    for raw in fields:
        field = raw[1:] if raw.startswith("\n") else raw
        if len(field) < 2:
            raise NotMeasured("lsof returned a malformed field record")
        tag, value = field[0], field[1:]
        if tag == "p" and value.isdecimal() and not expect_name:
            if pid is not None and not found.get(pid):
                raise NotMeasured("lsof returned a process without cwd or root")
            pid = int(value)
            found.setdefault(pid, [])
        elif tag == "f" and value in {"cwd", "rtd"} and pid is not None and not expect_name:
            expect_name = True
        elif tag == "n" and value and pid is not None and expect_name:
            found[pid].append(value)
            expect_name = False
        else:
            raise NotMeasured("lsof returned a malformed or incomplete field protocol")
    if expect_name or pid is None or not found.get(pid):
        raise NotMeasured("lsof returned an incomplete process listing")
    return found


def live_cwds(proc: Path = Path("/proc")) -> dict[int, list[str]]:
    """cwd and root of every readable process."""
    if not proc.is_dir():
        return _live_cwds_lsof()
    found: dict[int, list[str]] = {}
    for entry in proc.iterdir():
        if not entry.name.isdecimal():
            continue
        for link in ("cwd", "root"):
            try:
                found.setdefault(int(entry.name), []).append(os.readlink(entry / link))
            except OSError:
                pass
    return found


def _inside(path: str, root: Path) -> bool:
    return path == str(root) or path.startswith(str(root) + "/")


def _setuptools_build(path: Path, name: str) -> bool:
    """An ignored ``build/`` holding only ``bdist.*``/``lib*``, next to its project file."""
    build = path / name.rstrip("/")
    if build.name != "build" or not build.is_dir() or build.is_symlink():
        return False
    if not any((build.parent / marker).is_file() for marker in ("pyproject.toml", "setup.py")):
        return False
    return all(child.name.startswith(("bdist.", "lib")) for child in build.iterdir())


def _ignored_present(path: Path) -> list[str]:
    output = _git(path, "status", "--porcelain=v1", "-z", "--ignored=matching", "--untracked-files=all")
    names = [entry[3:] for entry in output.split("\0") if entry.startswith("!! ")]
    return [name for name in names
            if not REGENERABLE.intersection(Path(name.rstrip("/")).parts)
            and not any(part.endswith(".egg-info") for part in Path(name.rstrip("/")).parts)
            and not _setuptools_build(path, name)]


def assess(root: Path, entry: dict[str, str], *, base: str, project: str,
           claims: list[dict] | None, processes: dict[int, list[str]],
           merged_heads: frozenset[str] = frozenset(), mission: Any = None) -> dict:
    """Return the verdict for one worktree with every failed condition named."""
    path = Path(entry["worktree"])
    ref = entry.get("branch", "")
    branch = ref.removeprefix("refs/heads/") if ref else None
    head = entry.get("HEAD", "")
    refused: list[str] = []
    detail: dict = {}

    if "locked" in entry:
        refused.append("locked")
    if _inside(str(path), root):
        # e.g. `.sober/update-vanguard-releases/*`: owned by the project's release retention.
        refused.append("inside_canonical_checkout")

    tracked, untracked = local_changes(path)
    stray = sorted(name for name in untracked if Path(name).parts[0] != ".venv")
    ignored = _ignored_present(path)
    # The mission's recorded state decides first: parked is never collected; a terminal
    # mission (merged/closed/discarded) is collected with ALL its work archived, so local
    # changes and unpushed commits no longer keep the worktree alive.
    by_state = mission is not None and mission.collectable
    if mission is not None:
        detail["mission"] = mission.as_dict()
        if mission.parked:
            refused.append("parked")
    if (tracked or stray or ignored) and not by_state:
        refused.append("dirty")
        detail["dirty"] = sorted(tracked)[:5] + stray[:5] + ignored[:5]

    # HEAD exactly a merged PR's head: integrated, and its commits live on in refs/pull/<n>/head.
    by_pr = head in merged_heads
    unpushed = [] if by_pr or by_state else _git(path, "rev-list", "HEAD", "--not", "--remotes").split()
    if unpushed:
        refused.append("unpushed")
        detail["unpushed_commits"] = len(unpushed)

    ancestor = _git_ok(path, "merge-base", "--is-ancestor", "HEAD", base)
    content_merged = by_state or by_pr or ancestor or not pending_files(path, base, set(), set())
    if not content_merged:
        refused.append("not_merged")
    detail["merged_by"] = ("ancestor" if ancestor else "pr" if by_pr
                           else f"mission:{mission.state}" if by_state
                           else "content" if content_merged else None)

    if claims is not None:
        mine = [claim for claim in claims
                if not (by_state and int(claim["mission_id"]) == mission.mission_id)
                and ((claim["kind"] == "branch" and branch and claim["target"] == branch)
                     or (claim["kind"] == "path" and claim["target"].startswith("/")
                         and _inside(claim["target"], path)))]
        if any(claim["released_at"] is None for claim in mine):
            refused.append("claim_active")
        detail["claim"] = ("active" if "claim_active" in refused
                           else "released" if mine else "none")
    else:
        detail["claim"] = "no_ledger"

    users = sorted(pid for pid, links in processes.items() if any(_inside(link, path) for link in links))
    if users:
        refused.append("live_process")
        detail["pids"] = users

    return {"worktree": str(path), "branch": branch, "head": head,
            "eligible": not refused, "refused": refused, **detail}


def remote_pull_heads(root: Path) -> frozenset[str]:
    """Tips the host keeps forever under refs/pull/<n>/head (empty when it cannot be read)."""
    try:
        out = _git(root, "ls-remote", "origin", "refs/pull/*/head")
    except NotMeasured:
        return frozenset()
    return frozenset(line.split("\t", 1)[0] for line in out.splitlines() if "\t" in line)


def preserved_remotely(root: Path, head: str, *, base: str, pull_heads: frozenset[str]) -> bool:
    """HEAD is on the base or is a PR head the host keeps: an archive of it would add nothing."""
    return bool(head) and (head in pull_heads or _git_ok(root, "merge-base", "--is-ancestor", head, base))


def prune_archives(archive_root: Path, *, base: str = "origin/main", apply: bool) -> list[dict]:
    """Archives whose every byte lives elsewhere (no local diff, no untracked files, HEAD preserved
    on the remote) are removed: nothing is left behind, and nothing redundant is kept either."""
    pruned = []
    if not (archive_root / ARCHIVE_MARKER).is_file():
        return pruned
    pulls: dict[str, frozenset[str]] = {}
    candidates = [d for d in archive_root.iterdir() if d.is_dir() and (d / "verdict.json").is_file()]
    branches = archive_root / "branches"
    if branches.is_dir():
        candidates += [d for d in branches.iterdir() if d.is_dir() and (d / "verdict.json").is_file()]
    for item in sorted(candidates):
        try:
            verdict = json.loads((item / "verdict.json").read_text())
            root = Path(verdict["repository"])
            head = verdict.get("head") or verdict.get("tip") or ""
            if not root.is_dir():
                continue
            if (item / "untracked.tar.gz").exists():
                continue
            diff = item / "worktree.diff"
            if diff.exists() and diff.read_text().strip():
                continue
            if str(root) not in pulls:
                pulls[str(root)] = remote_pull_heads(root)
            if not pulls[str(root)]:
                continue  # without the host's PR refs nothing is provably redundant
            if not preserved_remotely(root, head, base=base, pull_heads=pulls[str(root)]):
                continue
        except (OSError, ValueError, KeyError, NotMeasured):
            continue
        if apply:
            shutil.rmtree(item)
        pruned.append({"archive": str(item), "head": head})
    return pruned


def archive(root: Path, verdict: dict, *, base: str, archive_root: Path) -> Path:
    """Write bundle, diffs, HEAD and status under the managed archive root."""
    archive_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    marker = archive_root / ARCHIVE_MARKER
    if archive_root.is_symlink() or (archive_root.stat().st_uid != os.getuid()):
        raise RuntimeError("archive root must be a real directory owned by this user")
    marker.touch(exist_ok=True)
    path = Path(verdict["worktree"])
    target = archive_root / f"{path.name}-{time.strftime('%Y%m%d-%H%M%S')}"
    target.mkdir(mode=0o700)
    head = verdict["head"]
    refs = ["HEAD", f"refs/heads/{verdict['branch']}"] if verdict["branch"] else ["HEAD"]
    _git(path, "bundle", "create", str(target / "branch.bundle"), *refs)
    _git(path, "bundle", "verify", str(target / "branch.bundle"))
    untracked = [name for name in _git(path, "ls-files", "--others", "--exclude-standard", "-z").split("\0")
                 if name and Path(name).parts[0] != ".venv"]
    if untracked:
        import tarfile

        with tarfile.open(target / "untracked.tar.gz", "w:gz") as tar:
            for name in untracked:
                tar.add(path / name, arcname=name, recursive=False)
    (target / "branch.diff").write_text(_git(path, "diff", "--binary", f"{base}...HEAD"))
    (target / "worktree.diff").write_text(_git(path, "diff", "--binary", "HEAD"))
    (target / "HEAD").write_text(head + "\n")
    (target / "status.txt").write_text(_git(path, "status", "--porcelain=v1", "--branch"))
    (target / "verdict.json").write_text(json.dumps({**verdict, "base": base,
                                                     "repository": str(root)}, indent=2))
    return target


# Refusals that only mean "work would be lost without an archive"; anything else
# (claim, live process, lock, canonical tree) keeps an ownerless worktree unadoptable.
_ADOPTABLE_REFUSALS = frozenset({"dirty", "unpushed", "not_merged"})


def _last_activity(path: Path) -> float:
    """Newest of HEAD's commit time and the mtime of every changed or untracked file."""
    stamps = [float(_git(path, "log", "-1", "--format=%ct", "HEAD").strip() or 0)]
    tracked, untracked = local_changes(path)
    for name in tracked | untracked:
        try:
            stamps.append((path / name).lstat().st_mtime)
        except OSError:
            pass
    return max(stamps)


def collect(root: Path, *, base: str, ledger: Path | None, apply: bool,
            archive_root: Path, proc: Path = Path("/proc"),
            adopt_abandoned_days: float | None = None, now: float | None = None,
            only_branches: set[str] | None = None, exempt_pids: frozenset[int] = frozenset()) -> dict:
    from .agent import project_identity

    project = project_identity(root)
    claims = ledger_claims(ledger, project)
    processes = {pid: links for pid, links in live_cwds(proc).items() if pid not in exempt_pids}
    try:
        merged_heads = frozenset(merged_pr_heads(root))
    except NotMeasured:
        merged_heads = frozenset()  # without the host, only ancestry and content prove a merge
    _git(root, "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}")
    from . import mission_lifecycle

    by_branch, by_worktree = mission_lifecycle.owners(ledger, claims)
    open_heads: set[str] | None = None
    if adopt_abandoned_days is not None:
        try:
            open_heads = {pr.get("headRefName") for pr in open_prs(root, "headRefName")}
        except NotMeasured:
            open_heads = None  # without the host's PR list nothing is provably abandoned
    states = mission_lifecycle.read_states(ledger, set(by_branch.values()) | set(by_worktree.values()))
    verdicts = []
    for position, entry in enumerate(list_worktrees(root)):
        path = entry.get("worktree")
        if position == 0 or "bare" in entry or not path:
            continue
        if only_branches is not None and entry.get("branch", "").removeprefix("refs/heads/") not in only_branches:
            continue
        if "prunable" in entry or not Path(path).is_dir():
            verdicts.append({"worktree": path, "eligible": False, "refused": ["missing"]})
            continue
        try:
            branch = entry.get("branch", "").removeprefix("refs/heads/") or None
            owner = by_worktree.get(path) or (by_branch.get(branch) if branch else None)
            verdict = assess(root, entry, base=base, project=project, claims=claims,
                             processes=processes, merged_heads=merged_heads,
                             mission=states.get(owner) if owner else None)
        except NotMeasured as exc:
            verdict = {"worktree": path, "eligible": False, "refused": ["not_measured"],
                       "error": str(exc)}
        if (not verdict["eligible"] and open_heads is not None and owner is None
                and set(verdict.get("refused", ())) <= _ADOPTABLE_REFUSALS
                and (branch is None or branch not in open_heads)):
            idle_days = ((now or time.time()) - _last_activity(Path(path))) / 86400
            if idle_days >= adopt_abandoned_days:
                verdict["abandoned_idle_days"] = round(idle_days, 1)
                if not apply or ledger is None:
                    verdict["would_adopt"] = True
                else:
                    from .ledger import Ledger

                    adopted = mission_lifecycle.adopt_discarded(
                        Ledger(ledger), title=f"adotado: worktree abandonado {Path(path).name}"[:240],
                        project=project, branch=branch, worktree=path)
                    verdict = assess(root, entry, base=base, project=project, claims=None,
                                     processes=processes, merged_heads=merged_heads, mission=adopted)
                    verdict["adopted_mission"] = adopted.mission_id
        if apply and verdict["eligible"]:
            verdict.update(_remove(root, verdict, base=base, archive_root=archive_root, proc=proc,
                                   ledger=ledger, exempt_pids=exempt_pids))
        verdicts.append(verdict)
    return {"repository": str(root), "base": base, "project": project,
            "ledger": str(ledger) if ledger else None, "applied": apply,
            "eligible": sum(v["eligible"] for v in verdicts), "worktrees": verdicts}


def _remove(root: Path, verdict: dict, *, base: str, archive_root: Path, proc: Path,
            ledger: Path | None = None, exempt_pids: frozenset[int] = frozenset()) -> dict:
    path = Path(verdict["worktree"])
    mission = verdict.get("mission")
    by_state = bool(mission and mission.get("collectable"))
    # Recheck the cheap, fast-changing conditions at the effect boundary.
    tracked, untracked = local_changes(path)
    if not by_state and (tracked or any(Path(name).parts[0] != ".venv" for name in untracked)):
        return {"removed": False, "refused": ["dirty_at_removal"], "eligible": False}
    if any(_inside(link, path) for pid, links in live_cwds(proc).items() if pid not in exempt_pids
           for link in links):
        return {"removed": False, "refused": ["live_process_at_removal"], "eligible": False}
    tracked, untracked = local_changes(path)
    unique = tracked or any(Path(name).parts[0] != ".venv" for name in untracked)
    if not unique and preserved_remotely(root, verdict["head"], base=base,
                                         pull_heads=remote_pull_heads(root)):
        archived = None  # every byte is on the remote already; nothing to keep, nothing left behind
    else:
        archived = archive(root, verdict, base=base, archive_root=archive_root)
    venv = path / ".venv"
    if venv.is_dir() and not venv.is_symlink() and not _git_ok(path, "check-ignore", "-q", ".venv"):
        shutil.rmtree(venv)  # untracked .venv would make `git worktree remove` refuse
    try:
        # --force only for a terminal mission, whose whole work the archive above now holds.
        _git(root, "worktree", "remove", *(["--force"] if by_state else []), str(path))
    except NotMeasured as exc:
        return {"removed": False, "archive": str(archived) if archived else None, "error": str(exc)}
    branch_deleted = False
    if verdict["branch"]:
        branch_deleted = _git_ok(root, "branch", "-D", verdict["branch"])
    if by_state and ledger is not None:
        from . import mission_lifecycle
        from .ledger import Ledger

        try:
            mission_lifecycle.record(Ledger(ledger), mission["mission_id"], "collected")
        except mission_lifecycle.InvalidTransition:
            pass  # another collector recorded it first
    return {"removed": True, "archive": str(archived) if archived else None,
            "branch_deleted": branch_deleted}


def own_process_tree(pid: int | None = None) -> frozenset[int]:
    """This process and its ancestors: the owner finishing its own scope, never a third party."""
    tree, current = set(), os.getpid() if pid is None else pid
    while current > 1 and current not in tree:
        tree.add(current)
        try:
            parent = subprocess.run(["ps", "-o", "ppid=", "-p", str(current)], capture_output=True,
                                    text=True, timeout=10).stdout.strip()
            current = int(parent) if parent else 0
        except (OSError, subprocess.SubprocessError, ValueError):
            break
    return frozenset(tree)


def release_branch_resources(root: Path, ledger: Path | None, branch: str, *,
                             archive_root: Path | None = None, base: str = "origin/main",
                             proc: Path = Path("/proc")) -> dict:
    """The mission's `Drop`: collect the worktrees of ``branch`` at the terminal transition itself.

    Same assessment and archive as the daily run, scoped to one branch. The caller's own
    process tree does not count as a live user; any other process inside still keeps it.
    """
    return collect(root, base=base, ledger=ledger, apply=True,
                   archive_root=archive_root or default_archive_root(), proc=proc,
                   only_branches={branch}, exempt_pids=own_process_tree())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="harness-worktree-gc", description=__doc__.splitlines()[0])
    parser.add_argument("--repo", type=Path, action="append",
                        help="repository (any of its worktrees); repeatable; default: cwd")
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--ledger", type=Path, default=None,
                        help="update ledger (default: $HARNESS_LEDGER or the canonical checkout's)")
    parser.add_argument("--archive-root", type=Path, default=default_archive_root())
    parser.add_argument("--registered", action="store_true",
                        help="every project in the harness ledger registry (the scheduled job's scope)")
    parser.add_argument("--adopt-abandoned-days", type=float, default=None,
                        help="give an ownerless worktree (no mission, PR, claim or live process) idle "
                             "this long a mission recorded as discarded, then collect it with its "
                             "work archived (owner decision 2026-10-30; dry-run only reports)")
    parser.add_argument("--prune-archives", action="store_true",
                        help="also remove archives whose content is all on the remote already")
    parser.add_argument("--apply", action="store_true", help="archive and remove (default: dry-run)")
    args = parser.parse_args(argv)
    from .agent import ledger_registry_path, resolve_ledger
    from .vulnerabilities import registered_projects

    repos = args.repo or []
    if args.registered:
        repos += [root for _identity, root in registered_projects(ledger_registry_path())]
    reports = []
    status = 0
    for repo in repos or [Path.cwd()]:
        try:
            root = repo_root(repo)
            try:
                ledger = resolve_ledger(args.ledger, root)
            except SystemExit:
                ledger = None
            reports.append(collect(root, base=args.base, ledger=ledger, apply=args.apply,
                                   archive_root=args.archive_root.expanduser(),
                                   adopt_abandoned_days=args.adopt_abandoned_days))
        except NotMeasured as exc:
            reports.append({"repository": str(repo), "error": str(exc)})
            status = 2
    if args.prune_archives:
        reports.append({"pruned_archives": prune_archives(args.archive_root.expanduser(), base=args.base,
                                                          apply=args.apply)})
    print(json.dumps(reports, indent=2, ensure_ascii=False))
    return status
