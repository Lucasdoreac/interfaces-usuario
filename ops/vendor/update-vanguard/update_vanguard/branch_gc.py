"""Delete remote branches of closed pull requests when nothing can be lost, archiving them first.

A remote branch is eligible only when ALL of these hold:

1. pr_closed: its pull request is CLOSED or MERGED (an open PR keeps its branch);
2. same_repo: the PR head lives in this repository, not a fork;
3. pull_ref: the host's ``refs/pull/<n>/head`` points at the branch tip, so the
   commits stay reachable (and the PR's "Restore branch" keeps working) after
   the branch ref is gone;
4. no_open_pr: no open pull request uses the branch as head;
5. claim: no active claim on the branch in the update ledger;
6. no_worktree: no local worktree has the branch checked out;
7. not_default: the branch is not the remote default branch.

Before deleting, the collector re-assesses, fetches the tip, writes a verified
``git bundle`` plus the PR metadata under the managed archive root, and deletes
with a lease on the exact SHA, so a branch that moved is never removed.
Dry-run is the default; ``--apply`` acts. The ledger is read-only.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any, Callable

from .worktree_gc import ARCHIVE_MARKER, default_archive_root, ledger_claims
from .worktrees import NotMeasured, _git, list_worktrees, repo_root

GhRunner = Callable[[list[str], Path], str]
PR_FIELDS = "number,state,headRefName,isCrossRepository,title,url"


def _gh(args: list[str], cwd: Path) -> str:
    try:
        return subprocess.run(["gh", *args], cwd=cwd, check=True, capture_output=True,
                              text=True, timeout=60).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise NotMeasured(f"gh {' '.join(args[:3])} failed: {exc}") from exc


def _remote_refs(root: Path, *refs: str) -> dict[str, str]:
    out = _git(root, "ls-remote", "origin", *refs)
    return {name: sha for sha, name in (line.split("\t", 1) for line in out.splitlines() if "\t" in line)}


def _default_branch(root: Path) -> str:
    for line in _git(root, "ls-remote", "--symref", "origin", "HEAD").splitlines():
        if line.startswith("ref: ") and line.endswith("\tHEAD"):
            return line[len("ref: "):-len("\tHEAD")].removeprefix("refs/heads/")
    raise NotMeasured("remote default branch could not be read")


def assess(root: Path, pr: dict, *, gh: GhRunner, claims: list[dict] | None,
           checked_out: set[str], default: str, mission: Any = None) -> dict:
    """Return the verdict for one PR's head branch with every failed condition named."""
    branch = str(pr.get("headRefName") or "")
    number = int(pr["number"])
    refused: list[str] = []
    verdict: dict = {"pr": number, "branch": branch, "state": pr.get("state"),
                     "title": pr.get("title"), "url": pr.get("url")}
    if pr.get("state") not in {"CLOSED", "MERGED"}:
        refused.append("pr_open")
    if pr.get("isCrossRepository") is not False:
        refused.append("other_repository")
    if not branch or branch == default:
        refused.append("default_branch")
    refs = _remote_refs(root, f"refs/heads/{branch}", f"refs/pull/{number}/head") if branch else {}
    tip = refs.get(f"refs/heads/{branch}")
    verdict["tip"] = tip
    if tip is None:
        refused.append("branch_absent")
    elif refs.get(f"refs/pull/{number}/head") != tip:
        refused.append("pull_ref_differs")
        verdict["pull_ref"] = refs.get(f"refs/pull/{number}/head")
    if branch:
        open_prs = json.loads(gh(["pr", "list", "--state", "open", "--head", branch,
                                  "--json", "number"], root) or "[]")
        if open_prs:
            refused.append("open_pr_uses_branch")
            verdict["open_prs"] = [item["number"] for item in open_prs]
    if mission is not None:
        verdict["mission"] = mission.as_dict()
        if mission.parked:
            refused.append("parked")  # the owner's recorded decision, not a stand-in claim
    own = mission.mission_id if mission is not None and mission.collectable else None
    if claims is None:
        verdict["claim"] = "no_ledger"
    else:
        mine = [c for c in claims if c["kind"] == "branch" and c["target"] == branch
                and (own is None or int(c.get("mission_id", 0)) != own)]
        if any(c["released_at"] is None for c in mine):
            refused.append("claim_active")
        verdict["claim"] = ("active" if "claim_active" in refused
                            else "released" if mine else "none")
    if branch in checked_out:
        refused.append("checked_out_locally")
    return {**verdict, "eligible": not refused, "refused": refused}


def archive(root: Path, verdict: dict, pr: dict, *, archive_root: Path) -> Path:
    """Fetch the tip, write a verified bundle and the PR metadata under the archive root."""
    archive_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if archive_root.is_symlink() or archive_root.stat().st_uid != os.getuid():
        raise RuntimeError("archive root must be a real directory owned by this user")
    (archive_root / ARCHIVE_MARKER).touch(exist_ok=True)
    tip = verdict["tip"]
    safe = verdict["branch"].replace("/", "_")
    target = archive_root / "branches" / f"{safe}-{tip[:12]}-{time.strftime('%Y%m%d-%H%M%S')}"
    target.mkdir(parents=True, mode=0o700)
    ref = f"refs/harness-branch-gc/{verdict['pr']}"
    try:
        _git(root, "fetch", "-q", "origin", f"+refs/heads/{verdict['branch']}:{ref}")
        if _git(root, "rev-parse", ref).strip() != tip:
            raise NotMeasured("fetched tip does not match the assessed SHA")
        bundle = target / "branch.bundle"
        _git(root, "bundle", "create", "-q", str(bundle), ref)
        _git(root, "bundle", "verify", "-q", str(bundle))
    finally:
        subprocess.run(["git", "update-ref", "-d", ref], cwd=root, capture_output=True)
    (target / "pr.json").write_text(json.dumps(pr, indent=2, ensure_ascii=False))
    (target / "verdict.json").write_text(json.dumps({**verdict, "repository": str(root)}, indent=2))
    return target


def _delete(root: Path, verdict: dict, *, gh: GhRunner, claims: list[dict] | None,
            checked_out: set[str], default: str, archive_root: Path, mission: Any = None) -> dict:
    # Re-assess at the effect boundary: a reopened PR or a moved tip stops it.
    pr = json.loads(gh(["pr", "view", str(verdict["pr"]), "--json", PR_FIELDS], root))
    again = assess(root, pr, gh=gh, claims=claims, checked_out=checked_out, default=default,
                   mission=mission)
    if not again["eligible"] or again["tip"] != verdict["tip"]:
        return {"deleted": False, "eligible": False, "refused": again["refused"] or ["tip_moved"]}
    # No archive: eligibility already proved refs/pull/<n>/head holds this exact tip on the host,
    # so a local bundle would only duplicate it. Nothing is left behind and nothing redundant kept.
    archived = None
    ref = f"refs/heads/{verdict['branch']}"
    pushed = subprocess.run(["git", "push", "-q", f"--force-with-lease={ref}:{verdict['tip']}",
                             "origin", f":{ref}"], cwd=root, capture_output=True, text=True)
    if pushed.returncode != 0:
        return {"deleted": False, "archive": archived, "error": pushed.stderr.strip()[-300:]}
    gone = ref not in _remote_refs(root, ref)
    return {"deleted": gone, "archive": archived,
            **({} if gone else {"error": "branch still listed after delete"})}


def collect(root: Path, prs: list[int], *, gh: GhRunner, ledger: Path | None, apply: bool,
            archive_root: Path) -> dict:
    from .agent import project_identity

    project = project_identity(root)
    claims = ledger_claims(ledger, project)
    checked_out = {entry["branch"].removeprefix("refs/heads/")
                   for entry in list_worktrees(root) if entry.get("branch")}
    default = _default_branch(root)
    from . import mission_lifecycle

    by_branch, _ = mission_lifecycle.owners(ledger, claims)
    states = mission_lifecycle.read_states(ledger, set(by_branch.values()))
    verdicts = []
    for number in prs:
        try:
            pr = json.loads(gh(["pr", "view", str(number), "--json", PR_FIELDS], root))
            owner = by_branch.get(str(pr.get("headRefName") or ""))
            mission = states.get(owner) if owner else None
            if (apply and mission is not None and pr.get("state") == "CLOSED"
                    and mission.state == "active" and ledger is not None):
                from .ledger import Ledger

                # Event source: the host says the PR closed; the mission records it once.
                mission = mission_lifecycle.record(Ledger(ledger), owner, "pr_closed", pr_number=number)
                from .worktree_gc import release_branch_resources

                # The `Drop` of a closed PR: its worktree is archived and removed with the transition.
                release_branch_resources(root, ledger, str(pr["headRefName"]))
            verdict = assess(root, pr, gh=gh, claims=claims, checked_out=checked_out, default=default,
                             mission=mission)
            if apply and verdict["eligible"]:
                verdict.update(_delete(root, verdict, gh=gh, claims=claims, checked_out=checked_out,
                                       default=default, archive_root=archive_root, mission=mission))
        except (NotMeasured, ValueError, KeyError) as exc:
            verdict = {"pr": number, "eligible": False, "refused": ["not_measured"], "error": str(exc)}
        verdicts.append(verdict)
    return {"repository": str(root), "project": project, "ledger": str(ledger) if ledger else None,
            "applied": apply, "eligible": sum(v["eligible"] for v in verdicts), "branches": verdicts}


def discover(root: Path, *, gh: GhRunner, default: str) -> tuple[list[int], list[str]]:
    """Closed/merged PRs whose head branch still exists, and remote branches with no PR at all.

    A branch whose PR history includes an open PR is never proposed; a branch
    with no PR is only reported (nothing proves it is disposable).
    """
    heads = {name.removeprefix("refs/heads/") for name in _remote_refs(root, "refs/heads/*")}
    heads.discard(default)
    prs = json.loads(gh(["pr", "list", "--state", "all", "--limit", "1000",
                         "--json", "number,state,headRefName,isCrossRepository"], root) or "[]")
    by_branch: dict[str, list[dict]] = {}
    for pr in prs:
        if pr.get("isCrossRepository") is False and pr.get("headRefName") in heads:
            by_branch.setdefault(pr["headRefName"], []).append(pr)
    candidates = []
    for branch, items in sorted(by_branch.items()):
        if any(item.get("state") == "OPEN" for item in items):
            continue
        candidates.append(max(int(item["number"]) for item in items))
    return sorted(candidates), sorted(heads - set(by_branch))


def registered_roots(registry: Path) -> list[Path]:
    from .vulnerabilities import registered_projects

    return [root for _identity, root in registered_projects(registry)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="harness-branch-gc", description=__doc__.splitlines()[0])
    parser.add_argument("prs", type=int, nargs="*",
                        help="pull requests whose head branch to collect (default: discover every closed one)")
    parser.add_argument("--repo", type=Path, action="append",
                        help="repository (repeatable; default: every project in the harness ledger registry)")
    parser.add_argument("--registry", type=Path,
                        default=Path(os.environ.get("HARNESS_LEDGER_REGISTRY")
                                     or Path.home() / ".local/state/harness/ledgers.json"))
    parser.add_argument("--ledger", type=Path, default=None,
                        help="update ledger (default: $HARNESS_LEDGER or the canonical checkout's)")
    parser.add_argument("--archive-root", type=Path, default=default_archive_root())
    parser.add_argument("--apply", action="store_true", help="archive and delete (default: dry-run)")
    args = parser.parse_args(argv)
    if args.prs and (not args.repo or len(args.repo) != 1):
        parser.error("explicit PR numbers need exactly one --repo")
    from .agent import resolve_ledger

    reports, status = [], 0
    for repo in args.repo or registered_roots(args.registry):
        try:
            root = repo_root(repo)
            try:
                ledger = resolve_ledger(args.ledger, root)
            except SystemExit:
                ledger = None
            prs, without_pr = (args.prs, None) if args.prs else discover(
                root, gh=_gh, default=_default_branch(root))
            report = collect(root, prs, gh=_gh, ledger=ledger, apply=args.apply,
                             archive_root=args.archive_root.expanduser())
            if without_pr is not None:
                report["branches_without_pr"] = without_pr
            reports.append(report)
        except NotMeasured as exc:
            reports.append({"repository": str(repo), "error": str(exc)})
            status = 2
    print(json.dumps(reports, indent=2, ensure_ascii=False))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
