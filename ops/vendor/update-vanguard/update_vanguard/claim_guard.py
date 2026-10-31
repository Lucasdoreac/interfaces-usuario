"""PARADIGMA: a write reaches Git only from the writer that holds its claim.

Claims in the canonical ledger were advisory: nothing stopped a second agent
from committing a file another mission held, or from committing files nobody
claimed. This guard turns them into a gate at two points:

- ``pre-commit`` (Git hook, every agent and human): each staged path must be
  claimed by this branch's mission, and by no other mission.
- ``agent-hook`` (PreToolUse of Claude Code and Codex): the same rule before an
  edit (Edit/Write, Codex ``apply_patch``), and no write inside a deployed
  release, by edit or shell. Other shell writes are caught by ``pre-commit``.
- ``check-pr`` and ``harness-agent gate`` (merge): the PR's files against the
  mission holding its branch. It also covers clones and runners whose commits
  never ran a hook.

A project takes part once its identity is bound to one ledger
(``harness-agent --ledger PATH ledger bind``). Unbound projects are not
adopted: the Claude hook lets them through, while an installed Git hook
refuses until the binding exists. A ledger that cannot be read, a schema this
core does not know, or a second ledger with live claims for the same identity
(a split ledger) is "not measured" and refuses, never passes.

The ledger is only queried (SELECT); the guard never writes or migrates it. There is no bypass switch: a mission that needs a file takes
the claim (``scripts/agent_overlap.py --claim ... --mission N --holder BRANCH``)
or gets it released by its holder.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import shlex
import sqlite3
import subprocess
import sys
from typing import Any, Sequence

from .agent import _canonical_checkout, bound_ledger, default_ledger_path, project_identity
from .ledger import SCHEMA_VERSION, claim_targets_overlap

ALLOW, BLOCK, NOT_ADOPTED = "allow", "block", "not_adopted"
HOOK_MARKER = "# managed-by: harness-claim-guard"
CLAUDE_MATCHER = "Edit|Write|MultiEdit|NotebookEdit|Bash"
CODEX_MATCHER = "Bash|apply_patch"


@dataclass
class Decision:
    status: str
    reasons: list[str] = field(default_factory=list)
    ledger: str | None = None
    branch: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"status": self.status, "reasons": self.reasons, "ledger": self.ledger, "branch": self.branch}


def _git(cwd: Path, *args: str) -> str | None:
    try:
        return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                              text=True, timeout=15).stdout
    except (OSError, subprocess.SubprocessError):
        return None


def _active_claims(ledger: Path, identity: str) -> list[dict[str, Any]]:
    """Active claims of one identity, read without writing or migrating the ledger.

    ``mode=rw`` never creates a database; only SELECTs run. ``mode=ro`` cannot
    open a WAL ledger whose shared-memory file is absent, and ``immutable``
    would skip claims still in the WAL.
    """
    conn = sqlite3.connect(f"file:{ledger}?mode=rw", uri=True, timeout=5)
    try:
        conn.row_factory = sqlite3.Row
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version < SCHEMA_VERSION:
            raise sqlite3.DatabaseError(f"schema v{version} < v{SCHEMA_VERSION}")
        rows = conn.execute(
            "SELECT claim_id,kind,target,mission_id,holder FROM update_claims "
            "WHERE project_root=? AND released_at IS NULL ORDER BY claim_id", (identity,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def _split_ledger(root: Path, bound: Path, identity: str) -> str | None:
    """A clone-local ledger other than the bound one that still holds live claims."""
    checkout = _canonical_checkout(root)
    if checkout is None:
        return None
    local = default_ledger_path(checkout)
    if not local.is_file() or local.resolve() == bound.resolve():
        return None
    try:
        live = _active_claims(local, identity)
    except sqlite3.Error:
        return f"{local} (unreadable second ledger for {identity})"
    if live:
        return f"{local} holds {len(live)} live claim(s) for {identity} outside the bound ledger {bound}"
    return None


def _describe(claim: dict[str, Any]) -> str:
    return f"{claim['target']} (mission {claim['mission_id']}, {claim['holder']})"


def evaluate(root: Path, paths: Sequence[str], *, branch: str | None) -> Decision:
    """Decide whether ``branch`` may write ``paths`` (repository-relative) in ``root``."""
    identity = project_identity(root)
    try:
        bound = bound_ledger(identity)
    except SystemExit as exc:
        return Decision(BLOCK, [f"not measured: {exc}"])
    if bound is None:
        return Decision(NOT_ADOPTED, [f"{identity} has no bound ledger "
                                      "(harness-agent --ledger PATH ledger bind)"])
    if not bound.is_file():
        return Decision(BLOCK, [f"not measured: bound ledger {bound} does not exist"], str(bound))
    split = _split_ledger(root, bound, identity)
    if split:
        return Decision(BLOCK, [f"not measured: split ledger — {split}"], str(bound))
    if not branch:
        return Decision(BLOCK, ["detached HEAD: claims are held per branch; commit on the mission branch"],
                        str(bound))
    try:
        active = _active_claims(bound, identity)
    except sqlite3.Error as exc:
        return Decision(BLOCK, [f"not measured: ledger {bound} unreadable ({exc})"], str(bound), branch)
    missions = {c["mission_id"] for c in active
                if (c["kind"] == "branch" and c["target"] == branch) or c["holder"] == branch}
    path_claims = [c for c in active if c["kind"] == "path"]
    reasons: list[str] = []
    for path in sorted(set(paths)):
        hits = [c for c in path_claims if claim_targets_overlap("path", path, c["target"])]
        foreign = [c for c in hits if c["mission_id"] not in missions and c["holder"] != branch]
        if foreign:
            reasons.append(f"{path}: claimed by " + "; ".join(_describe(c) for c in foreign))
        elif not hits:
            reasons.append(f"{path}: unclaimed — take it first "
                           f"(agent_overlap.py --claim {path} --mission N --holder {branch})")
    return Decision(BLOCK if reasons else ALLOW, reasons, str(bound), branch)


def _branch(cwd: Path) -> str | None:
    out = _git(cwd, "symbolic-ref", "--quiet", "--short", "HEAD")
    return out.strip() if out else None


def _integrated_merge_paths(root: Path) -> set[str] | None:
    """Staged paths a merge brings in unchanged from an already integrated base.

    Concluding `git merge origin/main` after a conflict stages every file the base
    changed, and none of them is a write by this branch: the base already carries
    them. A path counts as brought in only when its staged content equals the
    merged parent's AND that parent is in the remote default branch; merging an
    unintegrated branch, or a resolution that edits a base file, is checked in full.
    Returns an empty set when no merge is in progress, None when git cannot tell.
    """
    if _git(root, "rev-parse", "-q", "--verify", "MERGE_HEAD") is None:
        return set()
    base = _git(root, "rev-parse", "-q", "--verify", "refs/remotes/origin/HEAD")
    base_ref = "refs/remotes/origin/HEAD" if base else "refs/remotes/origin/main"
    try:
        integrated = subprocess.run(["git", "merge-base", "--is-ancestor", "MERGE_HEAD", base_ref],
                                    cwd=root, capture_output=True, timeout=15).returncode
    except (OSError, subprocess.SubprocessError):
        return None
    if integrated == 1:
        return set()
    if integrated != 0:
        return None
    staged = _git(root, "diff", "--cached", "--name-only", "-z", "--no-renames")
    differs = _git(root, "diff", "--cached", "--name-only", "-z", "--no-renames", "MERGE_HEAD")
    if staged is None or differs is None:
        return None
    return {p for p in staged.split("\0") if p} - {p for p in differs.split("\0") if p}


def pre_commit(cwd: Path) -> int:
    top = _git(cwd, "rev-parse", "--show-toplevel")
    if not top:
        print("harness-claim-guard: not inside a Git work tree", file=sys.stderr)
        return 1
    root = Path(top.strip())
    staged = _git(root, "diff", "--cached", "--name-only", "-z", "--no-renames")
    if staged is None:
        print("harness-claim-guard: could not read the staged paths; refusing", file=sys.stderr)
        return 1
    paths = [p for p in staged.split("\0") if p]
    integrated = _integrated_merge_paths(root)
    if integrated is None:
        print("harness-claim-guard: could not read the merge in progress; refusing", file=sys.stderr)
        return 1
    paths = [p for p in paths if p not in integrated]
    if not paths:
        return 0
    decision = evaluate(root, paths, branch=_branch(root))
    if decision.status == ALLOW:
        return 0
    # An installed hook means the project adopted the guard: unbound is a refusal too.
    print("harness-claim-guard: commit refused", file=sys.stderr)
    for reason in decision.reasons:
        print(f"  - {reason}", file=sys.stderr)
    return 1


RELEASES_DIR = "update-vanguard-releases"
_PATCH_FILE = re.compile(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$|^\*\*\* Move to: (.+)$", re.MULTILINE)
# Shell commands that write. Checked only when a deployed release is involved;
# reading a release (cat, rg, sed -n, git log) stays allowed.
# Verbs are matched on the command's non-path words only, so a path such as
# /tmp/pytest-of-x/... is never read as the verb ``pytest``.
_WRITE_VERBS = re.compile(
    r"\bpytest\b|\bpip3?\s+install\b|\buv\s+(?:sync|add|pip|run|lock)\b|\bnpm\b|\bmake\b"
    r"|\bgit\s+(?:commit|checkout|switch|reset|clean|stash|apply|am|merge|rebase|restore|pull|add|rm|mv)\b"
    r"|\b(?:rm|mv|cp|touch|mkdir|rmdir|chmod|chown|ln|tee|truncate|install|rsync)\b"
    r"|\bsed\s+(?:-[a-zA-Z]*i|--in-place)|\bperl\s+-[a-zA-Z]*i")


_HEREDOC = re.compile(r"(?<!<)<<(-?)[ \t]*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\2(?!<)")
_SEGMENT_START = re.compile(r"(?:&&|\|\||[;|&(`]|\$\()\s*")


def _without_cat_heredoc_bodies(command: str) -> str:
    """The command with the bodies of ``cat`` heredocs removed.

    A ``cat <<EOF`` body is data on stdin, so a path quoted in a note or commit
    message is not a target. Any other heredoc (``sh``, ``python3 -``) may be
    code and keeps its body. A line with several heredocs, or one that is never
    terminated, is left unchanged: not measured, so still checked.
    """
    lines = command.split("\n")
    kept: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        kept.append(line)
        index += 1
        found = list(_HEREDOC.finditer(line))
        if len(found) != 1:
            continue
        match = found[0]
        segment = _SEGMENT_START.split(line[:match.start()])[-1].split()
        if segment[:1] != ["cat"]:
            continue
        strip_tabs, delimiter = match.group(1) == "-", match.group(3)
        end = next((i for i in range(index, len(lines))
                    if (lines[i].lstrip("\t") if strip_tabs else lines[i]) == delimiter), None)
        if end is not None:
            index = end + 1
    return "\n".join(kept)


def _writes(command: str) -> bool:
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        tokens = command.split()
    words = " ".join(t for t in tokens if "/" not in t and not t.startswith(("~", ".")))
    return bool(_WRITE_VERBS.search(words) or _redirects_to_a_file(command))


def _redirects_to_a_file(command: str) -> bool:
    """An unquoted ``>``/``>>``/``&>`` to anything but /dev/null; ``2>&1`` duplicates, never writes."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        return ">" in command  # unbalanced quotes: not measured, so refuse
    for index, token in enumerate(tokens):
        if token in (">", ">>", ">|", "&>", "&>>") and index + 1 < len(tokens):
            if tokens[index + 1] != "/dev/null":
                return True
    return False


def _release_root(path: Path) -> Path | None:
    """The deployed release directory containing ``path``, if any."""
    parts = path.parts
    if RELEASES_DIR in parts:
        index = parts.index(RELEASES_DIR)
        if index + 1 < len(parts):
            return Path(*parts[:index + 2])
    for parent in (path, *path.parents):
        if (parent / ".update-vanguard-release.json").is_file():
            return parent
    return None


def _command_paths(command: str, cwd: Path) -> list[Path]:
    """Paths a command names, resolved: a symlink such as ``.sober/current`` is followed."""
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        tokens = command.split()
    paths = []
    for token in tokens:
        token = token.strip(";&|()")
        if "/" not in token and not token.startswith(("~", ".")):
            continue
        path = Path(os.path.expanduser(token))
        paths.append((path if path.is_absolute() else cwd / path).resolve())
    return paths


def release_write_refusal(command: str, cwd: Path) -> str | None:
    """A shell command that would write inside a deployed (production) release."""
    command = _without_cat_heredoc_bodies(command)
    candidates = [cwd.resolve(), *_command_paths(command, cwd)]
    release = next((root for root in map(_release_root, candidates) if root is not None), None)
    if release is None and f"/{RELEASES_DIR}/" not in command:
        return None
    if not _writes(command):
        return None
    return ("deployed releases are read-only: this command writes inside "
            f"{release or RELEASES_DIR}; run it in a worktree or a disposable copy "
            "of the exact SHA (git worktree add --detach <path> <sha>)")


def _edit_targets(event: dict[str, Any]) -> list[Path]:
    tool_input = event.get("tool_input") or {}
    cwd = Path(event.get("cwd") or os.getcwd())
    raw = [tool_input.get("file_path") or tool_input.get("notebook_path")]
    if event.get("tool_name") == "apply_patch":
        patch = str(tool_input.get("command") or tool_input.get("input") or "")
        raw = [a or b for a, b in _PATCH_FILE.findall(patch)]
    paths = []
    for item in raw:
        if item:
            path = Path(str(item).strip())
            paths.append(path if path.is_absolute() else cwd / path)
    return paths


def _claims_refusal(path: Path) -> list[str]:
    probe = path.parent
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    top = _git(probe, "rev-parse", "--show-toplevel")
    if not top:
        return []  # outside any repository: nothing to claim
    root = Path(top.strip())
    try:
        relative = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return []
    decision = evaluate(root, [relative], branch=_branch(root))
    return [] if decision.status in (ALLOW, NOT_ADOPTED) else decision.reasons


def agent_hook(stdin_text: str) -> int:
    """PreToolUse for Claude Code and Codex: exit 2 blocks the call and stderr reaches the agent.

    File edits (Edit/Write/MultiEdit/NotebookEdit, Codex ``apply_patch``) need the
    path's claim and may never land inside a deployed release. Shell commands
    (``Bash``) that write inside a deployed release are refused.
    """
    try:
        event = json.loads(stdin_text or "{}")
    except ValueError:
        print("harness-claim-guard: unreadable hook input; refusing the call", file=sys.stderr)
        return 2
    reasons: list[str] = []
    if event.get("tool_name") == "Bash":
        command = str((event.get("tool_input") or {}).get("command") or "")
        refusal = release_write_refusal(command, Path(event.get("cwd") or os.getcwd()))
        reasons += [refusal] if refusal else []
    else:
        for path in _edit_targets(event):
            if _release_root(path.resolve()) is not None:
                reasons.append(f"{path}: deployed releases are read-only")
            else:
                reasons += _claims_refusal(path)
    if not reasons:
        return 0
    print("harness-claim-guard: call refused", file=sys.stderr)
    for reason in reasons:
        print(f"  - {reason}", file=sys.stderr)
    return 2


def claim_scope_refusal(ledger: Path, identity: str, mission: int, holder: str) -> str | None:
    """Why ``mission``/``holder`` may not take claims for ``identity`` in ``ledger``, or None.

    Claims go to the ledger bound to the identity, and one mission is one job:
    one project and one holder. Reusing a mission for another project or
    holder mixes journals that release and audit treat as one unit.
    """
    try:
        bound = bound_ledger(identity)
    except SystemExit as exc:
        return f"not measured: {exc}"
    if bound is not None and bound.resolve() != ledger.resolve():
        return f"claims for {identity} belong to its bound ledger {bound}, not {ledger}"
    # Mission ids are per ledger: the same id in another ledger is a different mission.
    missing = (f"mission {mission} does not exist in {ledger}; allocate it in this ledger "
               "(harness-agent mission open --repo <this project>)")
    if not ledger.is_file():
        return missing
    try:
        conn = sqlite3.connect(f"file:{ledger}?mode=rw", uri=True, timeout=5)
        try:
            rows = conn.execute("SELECT DISTINCT project_root, holder FROM update_claims WHERE mission_id=?",
                                (mission,)).fetchall()
            known = conn.execute("SELECT 1 FROM update_missions WHERE mission_id=?", (mission,)).fetchone()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        return f"not measured: ledger {ledger} unreadable ({exc})"
    others = sorted({f"{h} @ {p}" for p, h in rows if (p, h) != (identity, holder)})
    if others:
        return (f"mission {mission} already belongs to {', '.join(others)}; "
                "allocate a new one (harness-agent mission new --title ...)")
    if known is None:
        return missing
    return None


def check_pr(repo: Path, pr: int) -> tuple[int, Decision]:
    """Decision for a PR's files against the mission holding its head branch.

    Exit 0 when allowed or the project is not adopted, 1 when refused, 2 when
    the PR could not be read (not measured).
    """
    view = _git_free(["gh", "pr", "view", str(pr), "--json", "headRefName"], repo)
    diff = _git_free(["gh", "pr", "diff", str(pr), "--name-only"], repo)
    try:
        branch = json.loads(view or "")["headRefName"]
    except (ValueError, KeyError, TypeError):
        branch = None
    if not branch or diff is None:
        return 2, Decision(BLOCK, [f"not measured: could not read PR #{pr} head or diff"])
    files = [line.strip() for line in diff.splitlines() if line.strip()]
    decision = evaluate(repo, files, branch=branch)
    return (1 if decision.status == BLOCK else 0), decision


def check_range(repo: Path, base: str, head: str, branch: str) -> tuple[int, Decision]:
    """Decision for the files a commit range changes, owned by ``branch``'s mission.

    For push gates that have no PR (a direct push of ``head``): the same rule as
    ``check-pr``. Exit 0 allowed or not adopted, 1 refused, 2 not measured.
    """
    diff = _git(repo, "diff", "--name-only", "--no-renames", f"{base}...{head}")
    if diff is None or not branch:
        return 2, Decision(BLOCK, [f"not measured: could not read {base}...{head} or the branch"])
    files = [line.strip() for line in diff.splitlines() if line.strip()]
    decision = evaluate(repo, files, branch=branch)
    return (1 if decision.status == BLOCK else 0), decision


def _git_free(argv: list[str], cwd: Path) -> str | None:
    try:
        return subprocess.run(argv, cwd=cwd, check=True, capture_output=True, text=True, timeout=120).stdout
    except (OSError, subprocess.SubprocessError):
        return None


def _command(action: str) -> str:
    script = Path(__file__).resolve().parents[1] / "scripts" / "harness-claim-guard"
    return f'"{sys.executable}" "{script}" {action}'


def install_git_hook(repo: Path) -> dict[str, Any]:
    """Write the managed pre-commit hook; never overwrite a hook someone else wrote."""
    hooks = _git(repo, "rev-parse", "--path-format=absolute", "--git-path", "hooks")
    if not hooks:
        raise SystemExit(f"harness-claim-guard: {repo} is not a Git repository")
    hook = Path(hooks.strip()) / "pre-commit"
    if hook.exists() and HOOK_MARKER not in hook.read_text(encoding="utf-8", errors="replace"):
        raise SystemExit(f"harness-claim-guard: {hook} exists and is not managed by this guard; "
                         "merge it by hand")
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text(f"#!/bin/sh\n{HOOK_MARKER}\nexec {_command('pre-commit')}\n", encoding="utf-8")
    hook.chmod(0o755)
    return {"installed": str(hook)}


def _install_agent_hook(path: Path, matcher: str) -> dict[str, Any]:
    """Merge one PreToolUse entry into a Claude settings or Codex hooks file, idempotently.

    Both agents read ``{"hooks": {"PreToolUse": [{matcher, hooks: [command]}]}}``.
    Codex runs a non-managed hook only after the owner trusts it in ``/hooks``.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except ValueError as exc:
        raise SystemExit(f"harness-claim-guard: {path} is not valid JSON: {exc}") from exc
    command = _command("agent-hook")
    entries = data.setdefault("hooks", {}).setdefault("PreToolUse", [])
    for entry in entries:
        for hook in entry.get("hooks", []):
            if "harness-claim-guard" in str(hook.get("command", "")):
                hook["command"] = command
                entry["matcher"] = matcher
                break
        else:
            continue
        break
    else:
        entries.append({"matcher": matcher, "hooks": [{"type": "command", "command": command}]})
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return {"installed": str(path), "matcher": matcher, "command": command}


def install_claude_hook(settings: Path) -> dict[str, Any]:
    return _install_agent_hook(settings, CLAUDE_MATCHER)


def install_codex_hook(hooks: Path) -> dict[str, Any]:
    return _install_agent_hook(hooks, CODEX_MATCHER)


# --- Reproducible installation: host hooks and per-project adoption --------
#
# Nothing here is a one-off manual step: `scripts/sync.py` installs and checks
# the host hooks, `scripts/bootstrap.py` adopts projects. Each `*_status` lists
# (ok, line) so the installers' `--check` fails on drift.

CLAUDE_SETTINGS = Path.home() / ".claude" / "settings.json"
CODEX_HOOKS = Path.home() / ".codex" / "hooks.json"


def _hook_entry_problem(path: Path, matcher: str) -> str | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return f"{path} is missing"
    except ValueError as exc:
        return f"{path} is not valid JSON: {exc}"
    expected = _command("agent-hook")
    for entry in (data.get("hooks") or {}).get("PreToolUse") or []:
        for hook in entry.get("hooks") or []:
            if "harness-claim-guard" in str(hook.get("command", "")):
                if hook.get("command") != expected or entry.get("matcher") != matcher:
                    return f"{path} has a stale harness-claim-guard entry (reinstall with sync.py --install)"
                return None
    return f"{path} has no harness-claim-guard PreToolUse entry"


def codex_hook_trust(hooks: Path = CODEX_HOOKS, *, timeout: float = 30) -> str:
    """Ask Codex itself (``codex app-server`` over stdio, ``hooks/list``) for our hook's trust.

    Returns trusted, untrusted, modified, absent, not_installed (no codex binary)
    or not_measured. Codex runs a non-managed hook only when it is trusted; the
    owner trusts it once per hook content in Codex's ``/hooks``.
    """
    import select
    import shutil
    import time

    if shutil.which("codex") is None:
        return "not_installed"
    try:
        process = subprocess.Popen(["codex", "app-server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL, text=True, bufsize=1, cwd=str(Path.home()))
    except OSError:
        return "not_measured"
    try:
        def send(message: dict[str, Any]) -> None:
            process.stdin.write(json.dumps(message) + "\n")
            process.stdin.flush()

        def read(wanted: int) -> dict[str, Any] | None:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                ready, _, _ = select.select([process.stdout], [], [], 0.5)
                if not ready:
                    continue
                line = process.stdout.readline()
                if not line:
                    return None
                try:
                    reply = json.loads(line)
                except ValueError:
                    continue
                if reply.get("id") == wanted:
                    return reply
            return None

        send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
              "params": {"clientInfo": {"name": "harness_claim_guard", "version": "1.0.0"}}})
        if "result" not in (read(1) or {}):  # an empty result object is a valid reply
            return "not_measured"
        send({"jsonrpc": "2.0", "method": "initialized"})
        send({"jsonrpc": "2.0", "id": 2, "method": "hooks/list", "params": {"cwds": [str(Path.home())]}})
        reply = read(2) or {}
        if "result" not in reply:
            return "not_measured"
        for group in reply["result"].get("data") or []:
            for hook in group.get("hooks") or []:
                if (str(hook.get("sourcePath")) == str(hooks) and hook.get("eventName") == "preToolUse"
                        and hook.get("matcher") == CODEX_MATCHER):
                    return str(hook.get("trustStatus") or "not_measured")
        return "absent"
    except (OSError, ValueError):
        return "not_measured"
    finally:
        process.kill()
        process.wait(timeout=5)


def host_status(claude_settings: Path = CLAUDE_SETTINGS, codex_hooks: Path = CODEX_HOOKS, *,
                codex_trust=codex_hook_trust) -> list[tuple[bool, str]]:
    result: list[tuple[bool, str]] = []
    for name, path, matcher in (("claude", claude_settings, CLAUDE_MATCHER), ("codex", codex_hooks, CODEX_MATCHER)):
        problem = _hook_entry_problem(path, matcher)
        result.append((problem is None, f"{name} hook: " + (problem or f"installed in {path}")))
    trust = codex_trust(codex_hooks)
    if trust == "not_installed":
        result.append((True, "codex hook trust: codex is not installed on this host"))
    elif trust == "trusted":
        result.append((True, "codex hook trust: trusted"))
    else:
        result.append((False, f"codex hook trust: {trust} — open Codex and trust it in /hooks"))
    return result


def install_host(claude_settings: Path = CLAUDE_SETTINGS, codex_hooks: Path = CODEX_HOOKS) -> list[str]:
    return [install_claude_hook(claude_settings)["installed"], install_codex_hook(codex_hooks)["installed"]]


GUARD_CALL = "harness-claim-guard pre-commit"


def _versioned_pre_commits(repo: Path) -> list[str]:
    """Tracked ``pre-commit`` files: a project that versions its hooks owns them."""
    listed = _git(repo, "ls-files", "-z")
    names = [n for n in (listed or "").split("\0") if n == "pre-commit" or n.endswith("/pre-commit")]
    return sorted(names)


def _calls_guard(path: Path) -> bool:
    try:
        return GUARD_CALL in path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


def adopt_project(root: Path) -> dict[str, Any]:
    """Bind the project to its canonical ledger and make every commit run the guard.

    A project that versions its own ``pre-commit`` keeps it: that file must call
    ``harness-claim-guard pre-commit`` and this clone's ``core.hooksPath`` is
    pointed at its directory (replacing the manual ``git config`` step). It is
    never overwritten; one that does not call the guard is refused. A project
    without versioned hooks gets the managed hook in ``.git/hooks``.
    """
    from .ledger import Ledger
    from .agent import bind_ledger

    top = _git(root, "rev-parse", "--show-toplevel")
    if not top:
        raise SystemExit(f"harness-claim-guard: {root} is not a Git repository")
    repo = Path(top.strip())
    identity = project_identity(repo)
    versioned = _versioned_pre_commits(repo)
    if versioned:
        calling = [name for name in versioned if _calls_guard(repo / name)]
        if len(calling) != 1:
            raise SystemExit(
                f"harness-claim-guard: versioned hooks {versioned} — exactly one must call "
                f"'{GUARD_CALL}' (project-owned files are never overwritten)")
    bound = bound_ledger(identity)
    if bound is None:
        checkout = _canonical_checkout(repo)
        ledger = default_ledger_path(checkout or repo)
        Ledger(ledger)  # creates the schema when absent; never migrates a newer one
        bind_ledger(identity, ledger)
        bound = ledger.resolve()
    if versioned:
        hooks_dir = str(Path(calling[0]).parent)
        if subprocess.run(["git", "config", "core.hooksPath", hooks_dir], cwd=repo,
                          capture_output=True, text=True).returncode != 0:
            raise SystemExit(f"harness-claim-guard: could not set core.hooksPath in {repo}")
        hook = str(repo / calling[0])
    else:
        hook = install_git_hook(repo)["installed"]
    return {"identity": identity, "ledger": str(bound), "hook": hook}


def project_status(root: Path) -> list[tuple[bool, str]]:
    top = _git(root, "rev-parse", "--show-toplevel")
    if not top:
        return [(False, f"{root} is not a Git repository")]
    repo = Path(top.strip())
    identity = project_identity(repo)
    try:
        bound = bound_ledger(identity)
    except SystemExit as exc:
        return [(False, f"ledger binding not measured: {exc}")]
    result = [(bound is not None and bound.is_file(),
               f"ledger binding: {identity} -> {bound}" if bound else f"ledger binding: {identity} is not bound")]
    hooks = _git(repo, "rev-parse", "--path-format=absolute", "--git-path", "hooks")
    hook = Path(hooks.strip()) / "pre-commit" if hooks else None
    text = hook.read_text(encoding="utf-8", errors="replace") if hook and hook.is_file() else ""
    managed = HOOK_MARKER in text and _command("pre-commit") in text
    versioned_ok = GUARD_CALL in text
    if versioned_ok and not managed:
        import shutil

        on_path = shutil.which("harness-claim-guard") is not None
        result.append((on_path, f"pre-commit guard: versioned hook {hook} calls the guard"
                       + ("" if on_path else "; harness-claim-guard is not on PATH (run sync.py --install)")))
    else:
        versioned = _versioned_pre_commits(repo)
        detail = (f"; versioned {versioned} must call '{GUARD_CALL}' and core.hooksPath point to it"
                  if versioned else "")
        result.append((managed, f"pre-commit guard: {'installed' if managed else 'missing or stale'} at {hook}{detail}"))
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="harness-claim-guard", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("pre-commit", help="Git hook: staged paths must be claimed by this branch's mission")
    sub.add_parser("agent-hook", help="PreToolUse for Claude and Codex: claims on edits, no writes in releases")
    sub.add_parser("claude-hook", help="alias of agent-hook (settings written before it existed)")
    check = sub.add_parser("check", help="report the decision for paths without blocking anything")
    check.add_argument("paths", nargs="+")
    check.add_argument("--repo", type=Path, default=Path.cwd())
    pr_check = sub.add_parser("check-pr", help="merge gate: the PR's files against its branch's mission")
    pr_check.add_argument("--pr", type=int, required=True)
    pr_check.add_argument("--repo", type=Path, default=Path.cwd())
    range_check = sub.add_parser("check-range", help="push gate: files of base...head against --branch's mission")
    range_check.add_argument("--repo", type=Path, default=Path.cwd())
    range_check.add_argument("--base", required=True)
    range_check.add_argument("--head", required=True)
    range_check.add_argument("--branch", required=True)
    git_hook = sub.add_parser("install-git-hook", help="write the managed pre-commit hook")
    git_hook.add_argument("--repo", type=Path, default=Path.cwd())
    claude = sub.add_parser("install-claude-hook", help="merge the PreToolUse entry into Claude settings")
    claude.add_argument("--settings", type=Path, default=Path.home() / ".claude" / "settings.json")
    codex = sub.add_parser("install-codex-hook", help="merge the PreToolUse entry into Codex hooks.json")
    codex.add_argument("--hooks", type=Path, default=Path.home() / ".codex" / "hooks.json")
    sub.add_parser("install-host", help="install the Claude and Codex hooks (used by sync.py --install)")
    sub.add_parser("host-status", help="check host hooks and Codex trust (used by sync.py --check)")
    adopt = sub.add_parser("adopt", help="bind a project's ledger and install its pre-commit guard")
    adopt.add_argument("--repo", type=Path, default=Path.cwd())
    status = sub.add_parser("project-status", help="check a project's ledger binding and pre-commit guard")
    status.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    if args.action in ("host-status", "project-status"):
        lines = host_status() if args.action == "host-status" else project_status(args.repo)
        for ok, line in lines:
            print(("OK " if ok else "DRIFT: ") + line)
        return 0 if all(ok for ok, _ in lines) else 1
    if args.action == "install-host":
        print(json.dumps(install_host()))
        return 0
    if args.action == "adopt":
        print(json.dumps(adopt_project(args.repo)))
        return 0
    if args.action == "pre-commit":
        return pre_commit(Path.cwd())
    if args.action in ("agent-hook", "claude-hook"):
        return agent_hook(sys.stdin.read())
    if args.action == "check":
        decision = evaluate(args.repo, args.paths, branch=_branch(args.repo))
        print(json.dumps(decision.as_dict(), indent=2))
        return 0 if decision.status == ALLOW else 1
    if args.action == "check-pr":
        code, decision = check_pr(args.repo, args.pr)
        print(json.dumps(decision.as_dict(), indent=2))
        return code
    if args.action == "check-range":
        code, decision = check_range(args.repo, args.base, args.head, args.branch)
        print(json.dumps(decision.as_dict(), indent=2))
        return code
    if args.action == "install-git-hook":
        print(json.dumps(install_git_hook(args.repo)))
        return 0
    if args.action == "install-codex-hook":
        print(json.dumps(install_codex_hook(args.hooks)))
        return 0
    print(json.dumps(install_claude_hook(args.settings)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
