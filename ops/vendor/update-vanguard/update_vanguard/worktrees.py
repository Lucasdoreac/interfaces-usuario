"""Git worktree measurements shared by the overlap checker and the worktree collector.

A file is pending on a worktree when it was committed since the merge base with
the base ref or changed locally, and its content still differs from the base
tip; content already on the base (for example after a squash merge) is not.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess

ARG_CHUNK = 500


class NotMeasured(RuntimeError):
    """A source of writers could not be read."""


def _run(args: list[str], cwd: Path) -> str:
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout


def _git(cwd: Path, *args: str) -> str:
    try:
        return _run(["git", *args], cwd)
    except subprocess.CalledProcessError as exc:
        raise NotMeasured(f"git {' '.join(args[:3])} failed in {cwd}: {exc.stderr.strip()[:200]}") from exc


def _names(output: str) -> set[str]:
    return {name for name in output.split("\0") if name}


def _chunks(items: list[str]):
    for start in range(0, len(items), ARG_CHUNK):
        yield items[start:start + ARG_CHUNK]


PR_FIELDS = "number,title,headRefName,headRefOid,url,isDraft,files"


def open_prs(root: Path, fields: str = PR_FIELDS) -> list[dict]:
    """Open pull requests of the repository at ``root`` as `gh pr list --json` reports them."""
    try:
        out = _run(["gh", "pr", "list", "--state", "open", "--limit", "200", "--json", fields], root)
    except FileNotFoundError as exc:
        raise NotMeasured("gh is not installed; pass --no-prs to measure worktrees only") from exc
    except subprocess.CalledProcessError as exc:
        raise NotMeasured(f"gh pr list failed: {exc.stderr.strip()[:200]}") from exc
    try:
        return json.loads(out)
    except json.JSONDecodeError as exc:
        raise NotMeasured("gh pr list returned invalid JSON") from exc


def merged_pr_heads(root: Path) -> set[str]:
    """Head SHAs of the repository's merged pull requests.

    A squash merge leaves the branch's own commits outside every remote branch
    and its files diverging from the base as soon as the base edits them again;
    the merged PR whose head is exactly a worktree's HEAD is the proof that its
    work is integrated, and the host keeps those commits under refs/pull/<n>/head.
    """
    try:
        out = _run(["gh", "pr", "list", "--state", "merged", "--limit", "1000",
                    "--json", "headRefOid"], root)
    except FileNotFoundError as exc:
        raise NotMeasured("gh is not installed") from exc
    except subprocess.CalledProcessError as exc:
        raise NotMeasured(f"gh pr list failed: {exc.stderr.strip()[:200]}") from exc
    try:
        return {pr["headRefOid"] for pr in json.loads(out) if pr.get("headRefOid")}
    except (json.JSONDecodeError, TypeError, KeyError) as exc:
        raise NotMeasured("gh pr list returned invalid JSON") from exc


def repo_root(path: Path) -> Path:
    return Path(_git(path, "rev-parse", "--show-toplevel").strip())


def default_base(root: Path) -> str:
    try:
        ref = _run(["git", "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"], root).strip()
    except subprocess.CalledProcessError:
        ref = ""
    return ref or "origin/main"


def list_worktrees(root: Path) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in _git(root, "worktree", "list", "--porcelain").splitlines() + [""]:
        if not line:
            if current:
                entries.append(current)
            current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value
    return entries


def local_changes(path: Path) -> tuple[set[str], set[str]]:
    """Tracked files changed in the index or working tree, and untracked files."""
    tracked: set[str] = set()
    untracked: set[str] = set()
    fields = _git(path, "status", "--porcelain=v1", "-z", "--untracked-files=all").split("\0")
    index = 0
    while index < len(fields):
        entry = fields[index]
        index += 1
        if not entry:
            continue
        code, name = entry[:2], entry[3:]
        (untracked if code == "??" else tracked).add(name)
        if code[0] in "RC":  # a rename's source path follows as its own field
            if index < len(fields) and fields[index]:
                tracked.add(fields[index])
            index += 1
    return tracked, untracked


def _same_as_base(path: Path, base: str, names: list[str]) -> set[str]:
    """Untracked files whose bytes equal the blob at the same path on the base."""
    in_base: dict[str, str] = {}
    for chunk in _chunks(names):
        for record in _names(_git(path, "ls-tree", "-z", base, "--", *chunk)):
            meta, _, name = record.partition("\t")
            in_base[name] = meta.split()[2]
    candidates = [name for name in names if name in in_base]
    same: set[str] = set()
    for chunk in _chunks(candidates):
        hashes = _git(path, "hash-object", "--", *chunk).split()
        same |= {name for name, digest in zip(chunk, hashes) if digest == in_base[name]}
    return same


def pending_files(path: Path, base: str, tracked: set[str], untracked: set[str]) -> set[str]:
    committed = _names(_git(path, "diff", "--name-only", "-z", f"{base}...HEAD"))
    differs = _names(_git(path, "diff", "--name-only", "-z", base))  # working tree vs base tip
    new = sorted(untracked)
    return ((committed | tracked) & differs) | (untracked - _same_as_base(path, base, new))
