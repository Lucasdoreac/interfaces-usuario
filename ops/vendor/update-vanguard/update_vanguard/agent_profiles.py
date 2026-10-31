"""PARADIGMA: one run contract for every coding agent; each CLI gets a thin adapter.

A profile states what an unattended run may use. The harness owns it and every
agent follows it, instead of each project hand-writing a different argv per CLI:

``batch``
    No MCP servers (a coding mission does not need the owner's connectors, and
    each one is a resident process on an 8 GB host). Writes only inside the
    mission worktree, its Git dirs (a linked worktree commits through
    ``.git/worktrees/<name>`` and the common ``.git``) and the claims ledger.
    No network unless the caller declares it. The final message goes to a file.

An adapter that cannot enforce a rule says so in ``Plan.unenforced`` rather than
pretending: Claude's print mode has no network sandbox.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

PROFILES = frozenset({"batch"})
AGENTS = frozenset({"codex", "claude"})


@dataclass(frozen=True)
class Plan:
    argv: list[str]
    #: Where the adapter sends stdout; ``None`` when the CLI writes the output file itself.
    stdout_to: Path | None
    writable: list[Path]
    unenforced: list[str] = field(default_factory=list)


def _git_dir(worktree: Path, flag: str) -> Path:
    out = subprocess.run(["git", "-C", str(worktree), "rev-parse", "--path-format=absolute", flag],
                         capture_output=True, text=True, check=True).stdout.strip()
    return Path(out)


def writable_dirs(worktree: Path, ledger: Path, output: Path) -> list[Path]:
    """Every directory a batch run must write, deduplicated, in a stable order."""
    dirs = [worktree, _git_dir(worktree, "--git-dir"), _git_dir(worktree, "--git-common-dir"),
            ledger.parent, output.parent]
    seen: list[Path] = []
    for path in (d.resolve() for d in dirs):
        if path not in seen:
            seen.append(path)
    return seen


def plan(agent: str, profile: str, *, worktree: Path, ledger: Path, output: Path,
         prompt: str, network: bool = False) -> Plan:
    if agent not in AGENTS:
        raise ValueError(f"unknown agent {agent!r}; supported: {sorted(AGENTS)}")
    if profile not in PROFILES:
        raise ValueError(f"unknown profile {profile!r}; supported: {sorted(PROFILES)}")
    if not prompt.strip():
        raise ValueError("a batch run needs a prompt")
    worktree = worktree.resolve()
    writable = writable_dirs(worktree, ledger, output)
    if agent == "codex":
        argv = ["codex", "exec", "-c", "mcp_servers={}", "-s", "workspace-write", "-C", str(worktree)]
        if network:
            argv += ["-c", "sandbox_workspace_write.network_access=true"]
        for path in writable[1:]:
            argv += ["--add-dir", str(path)]
        return Plan(argv + ["-o", str(output), prompt], None, writable)
    argv = ["claude", "-p", prompt, "--strict-mcp-config",
            "--mcp-config", json.dumps({"mcpServers": {}}),
            "--permission-mode", "acceptEdits", "--output-format", "text"]
    for path in writable[1:]:
        argv += ["--add-dir", str(path)]
    unenforced = [] if network else ["network: claude -p has no network sandbox"]
    return Plan(argv, output, writable, unenforced)
