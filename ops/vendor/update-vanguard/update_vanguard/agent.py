"""PARADIGMA: one agent run holds its file/branch claims in the canonical ledger.

``harness-agent start`` takes the mission's claims (all or nothing), runs the
command through ``harness-admit run`` and records the outcome as a mission
event. ``harness-agent wait`` blocks on the local ledger until the mission's
terminal event or ``woken`` arrives: on Linux the kernel (inotify on the
ledger directory) wakes it; elsewhere it re-reads the local ledger with a
bounded backoff. Neither path touches the network.

Claim lifetime: a run with ``--worktree`` holds its claims until the PR is
merged (``release --merged-pr``) or the owner discards the candidate
(``release --discard``); a run without a worktree releases on exit. Releasing
only changes ledger rows; worktrees and Git changes are never touched.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
from pathlib import Path
import re
import select
import signal
import struct
import subprocess
import sys
import tomllib
import time
from datetime import datetime
from typing import Any, Callable, Protocol, Sequence
from uuid import uuid4

from .ledger import (FAILURE_CLASSIFICATION, ClaimAuthorityError, ClaimConflictError, Ledger,
                     _derived_event_id)
from .gate import run_gate
from .quota import Snapshot, Window, select as select_quota

EXIT_FAILED = 1
EXIT_REFUSED = 75  # EX_TEMPFAIL: a claim is held by another mission; retry later.
EXIT_TIMEOUT = 124
TERMINAL_EVENTS = frozenset({"completed", "failed"})
COMPLETED_STATUSES = frozenset({"ENTREGUE", "COMPLETED", "OK", "DONE"})
ADMIT = Path(__file__).resolve().parent.parent / "scripts" / "harness-admit"
_SAFETY_RECHECK_S = 30.0  # even with inotify, re-read the ledger at least this often
_MAX_BACKOFF_S = 2.0
# A worker records where it is; lifecycle, gate and merge facts have their own writers.
WORKER_STAGES = ("diagnose", "repair", "validate", "review")
WORKER_NEXT_STEPS = ("diagnose", "review", "repair", "validate", "retry", "reconcile")
_SESSION = re.compile(r"\b([0-9a-f]{8}(?:-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})?)\b")


def record_worker_checkpoint(ledger: Ledger, mission_id: int, *, by: str, stage: str, next_step: str,
                             error_type: str | None = None, head_sha: str | None = None,
                             pr_number: int | None = None, files: Sequence[str] = ()) -> dict[str, Any]:
    """Append one worker progress checkpoint, or refuse with the reason (ClaimAuthorityError).

    Only the holder of an active claim of a mission this ledger holds, and that is not
    terminal, may write it. The classification is the harness's for ``error_type``.
    """
    from . import mission_lifecycle

    if stage not in WORKER_STAGES or next_step not in WORKER_NEXT_STEPS:
        raise ValueError("worker checkpoint stage or next step is not a worker one")
    if not ledger.has_mission(mission_id):
        raise ClaimAuthorityError(f"this ledger does not hold mission {mission_id}")
    current = mission_lifecycle.state(ledger, mission_id)
    if current.state != "active":
        raise ClaimAuthorityError(f"mission {mission_id} is {current.state}")
    holders = {claim["holder"] for claim in ledger.claims(mission_id=mission_id)}
    if by not in holders:
        raise ClaimAuthorityError(f"{by!r} holds no active claim of mission {mission_id}")
    checkpoint: dict[str, Any] = {"stage": stage, "writer": "worker", "actor": by, "next_step": next_step}
    if error_type is not None:
        if error_type not in FAILURE_CLASSIFICATION:
            raise ValueError(f"error type {error_type!r} is not one the harness produces; "
                             f"known: {', '.join(sorted(FAILURE_CLASSIFICATION))}")
        checkpoint["error_type"] = error_type
        checkpoint["classification"] = FAILURE_CLASSIFICATION[error_type]
    if head_sha is not None:
        checkpoint["head_sha"] = head_sha
    if pr_number is not None:
        checkpoint["pr_number"] = pr_number
    if files:
        checkpoint["files"] = list(files)
    ledger.record_mission_event(job_id=None, source_sha=None, mission_id=mission_id,
                                event_id=uuid4().hex, event_type="checkpoint", checkpoint=checkpoint)
    return {"mission_id": mission_id, "checkpoint": checkpoint}


class Watcher(Protocol):
    def wait(self, timeout: float) -> None: ...
    def close(self) -> None: ...


class _Inotify:
    """Kernel notification for content written to one file (or its SQLite WAL).

    The directory is watched because SQLite deletes and recreates the WAL, but
    only IN_MODIFY/IN_MOVED_TO on those names wake the waiter: a reader opening,
    closing or touching the shared-memory file must not wake itself.
    """

    _MASK = 0x2 | 0x80  # IN_MODIFY | IN_MOVED_TO

    def __init__(self, path: Path):
        self.names = {os.fsencode(path.name), os.fsencode(path.name + "-wal")}
        libc = ctypes.CDLL(None, use_errno=True)
        self.fd = libc.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)
        if self.fd < 0:
            raise OSError(ctypes.get_errno(), "inotify_init1 failed")
        if libc.inotify_add_watch(self.fd, os.fsencode(str(path.parent)), self._MASK) < 0:
            errno = ctypes.get_errno()
            os.close(self.fd)
            raise OSError(errno, "inotify_add_watch failed")

    def _relevant(self) -> bool:
        found = False
        try:
            while buffer := os.read(self.fd, 65536):
                offset = 0
                while offset + 16 <= len(buffer):
                    _wd, _mask, _cookie, length = struct.unpack_from("iIII", buffer, offset)
                    name = buffer[offset + 16:offset + 16 + length].rstrip(b"\0")
                    found = found or name in self.names
                    offset += 16 + length
        except BlockingIOError:
            pass
        return found

    def wait(self, timeout: float) -> None:
        deadline = time.monotonic() + max(0.0, timeout)
        while True:
            ready, _, _ = select.select([self.fd], [], [], max(0.0, deadline - time.monotonic()))
            if not ready or self._relevant() or time.monotonic() >= deadline:
                return

    def close(self) -> None:
        os.close(self.fd)


class _Backoff:
    """Fallback without kernel notification: bounded backoff over the local file."""

    def __init__(self, sleep: Callable[[float], None] = time.sleep):
        self.delay, self.sleep = 0.05, sleep

    def wait(self, timeout: float) -> None:
        self.sleep(max(0.0, min(self.delay, timeout)))
        self.delay = min(self.delay * 2, _MAX_BACKOFF_S)

    def close(self) -> None:
        pass


def watch(path: Path) -> Watcher:
    """Wake on writes to ``path``; bounded local backoff where inotify is unavailable."""
    if sys.platform.startswith("linux"):
        try:
            return _Inotify(path)
        except (OSError, AttributeError):
            pass
    return _Backoff()


def _wake_event(ledger: Ledger, mission_id: int, *, since: float,
                types: frozenset[str]) -> dict[str, Any] | None:
    """The first terminal event, or a ``woken`` that answers the latest wait."""
    events = [event for event in ledger.mission_events(mission_id) if event["created_at"] > since]
    waits = [event["created_at"] for event in events if event["event_type"] == "waiting"]
    last_wait = waits[-1] if waits else since
    for event in events:
        if event["event_type"] in TERMINAL_EVENTS & types:
            return event
        if event["event_type"] == "woken" and "woken" in types and event["created_at"] >= last_wait:
            return event
    return None


def wait_for_mission(ledger: Ledger, mission_id: int, *, timeout: float | None, since: float = 0.0,
                     types: frozenset[str] = TERMINAL_EVENTS | {"woken"},
                     watcher_factory: Callable[[Path], Watcher] = watch,
                     clock: Callable[[], float] = time.monotonic) -> dict[str, Any] | None:
    """Block until the mission's next wake event; None on timeout."""
    deadline = None if timeout is None else clock() + timeout
    # Watch before the first read so a write between read and wait still wakes us.
    watcher = watcher_factory(ledger.path)
    try:
        while True:
            event = _wake_event(ledger, mission_id, since=since, types=types)
            if event is not None:
                return event
            remaining = _SAFETY_RECHECK_S if deadline is None else deadline - clock()
            if remaining <= 0:
                return None
            watcher.wait(min(remaining, _SAFETY_RECHECK_S))
    finally:
        watcher.close()


def _git(path: Path, *args: str) -> str | None:
    try:
        return subprocess.run(["git", *args], cwd=path, check=True, capture_output=True,
                              text=True, timeout=15).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def _canonical_checkout(base: Path) -> Path | None:
    """The checkout that owns the Git common dir, shared by all of its worktrees."""
    common = _git(base, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if not common:
        return None
    common_path = Path(common)
    return common_path.parent if common_path.name == ".git" else common_path


def ledger_registry_path() -> Path:
    """Per-user map of project identity -> the one ledger every clone of it must use.

    Without it each clone resolves its own ``.sober`` ledger, so claims taken in
    one clone of a remote are invisible to another clone of the same remote.
    """
    if os.environ.get("HARNESS_LEDGER_REGISTRY"):
        return Path(os.environ["HARNESS_LEDGER_REGISTRY"])
    state = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(state) / "harness" / "ledgers.json"


def _read_registry(path: Path) -> dict[str, str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        raise SystemExit(f"harness-agent: ledger registry {path} unreadable: {exc}") from exc
    if not isinstance(data, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in data.items()):
        raise SystemExit(f"harness-agent: ledger registry {path} must map identity strings to ledger paths")
    return data


def bound_ledger(identity: str) -> Path | None:
    """The ledger bound to this project identity, or None when the project is not bound."""
    value = _read_registry(ledger_registry_path()).get(identity)
    return Path(value) if value else None


def bind_ledger(identity: str, ledger: Path, *, replace: bool = False) -> dict[str, Any]:
    """Bind one identity to one absolute ledger path; a different existing binding needs ``replace``."""
    ledger = ledger.expanduser().resolve()
    if not ledger.is_file():
        raise SystemExit(f"harness-agent: ledger {ledger} does not exist; bind an existing ledger")
    path = ledger_registry_path()
    registry = _read_registry(path)
    previous = registry.get(identity)
    if previous and Path(previous) != ledger and not replace:
        raise SystemExit(f"harness-agent: {identity} is already bound to {previous}; pass --replace to rebind")
    registry[identity] = str(ledger)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return {"identity": identity, "ledger": str(ledger), "previous": previous}


def default_ledger_path(checkout: Path) -> Path:
    """Local fallback path, independent of explicit or bound ledger selection."""
    return checkout / ".sober" / "update-vanguard.sqlite3"


def resolve_ledger(explicit: Path | None, base: Path) -> Path:
    """``--ledger``, else $HARNESS_LEDGER, else the ledger bound to the project's
    identity, else the canonical checkout's update ledger."""
    if explicit is not None:
        return explicit.resolve()
    if os.environ.get("HARNESS_LEDGER"):
        return Path(os.environ["HARNESS_LEDGER"]).resolve()
    if _canonical_checkout(base) is not None and (bound := bound_ledger(project_identity(base))):
        return bound
    checkout = _canonical_checkout(base)
    if checkout is None:
        raise SystemExit("harness-agent: not in a Git checkout; pass --ledger or set HARNESS_LEDGER")
    return default_ledger_path(checkout)


def project_identity(base: Path) -> str:
    """Claim space shared by every worktree of one repository.

    The origin identity sober-updates uses when the remote has a host; for a
    local or missing remote, the canonical checkout path instead of the
    worktree's own path, so two worktrees of the same repository collide.
    """
    from .capability import _project_identity

    identity = _project_identity(base)
    if identity.startswith("git:"):
        return identity
    checkout = _canonical_checkout(base)
    return str(checkout.resolve()) if checkout is not None else identity


def _claim_path(text: str, worktree: Path | None) -> str:
    """Paths inside the worktree become repository-relative, so worktrees collide."""
    path = Path(text)
    if worktree is not None:
        absolute = path if path.is_absolute() else worktree / path
        try:
            return absolute.resolve().relative_to(worktree.resolve()).as_posix()
        except ValueError:
            pass
    return path.resolve().as_posix() if path.is_absolute() else text


def report_status(path: Path) -> str | None:
    """The value of a first line ``STATUS: X``; None while the report is absent or partial."""
    try:
        with path.open(encoding="utf-8") as handle:
            first = handle.readline()
    except (OSError, UnicodeError):
        return None
    match = re.fullmatch(r"STATUS:\s*([A-Za-z_]+)\s*", first)
    return match.group(1).upper() if match else None


def wait_for_report(path: Path, *, timeout: float, watcher_factory: Callable[[Path], Watcher] = watch,
                    clock: Callable[[], float] = time.monotonic) -> str | None:
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = clock() + timeout
    watcher = watcher_factory(path)
    try:
        while True:
            status = report_status(path)
            if status is not None:
                return status
            remaining = deadline - clock()
            if remaining <= 0:
                return None
            watcher.wait(min(remaining, _SAFETY_RECHECK_S))
    finally:
        watcher.close()


def _is_background_claude(command: Sequence[str]) -> bool:
    return bool(command) and Path(command[0]).name == "claude" and bool({"--bg", "--background"} & set(command))


def admitted_runner(command: Sequence[str], *, mem: str, job: str, capture: bool,
                    cwd: Path | None = None) -> tuple[int, str]:
    """Run through the host admission point; capture stdout only to find a session id.

    stdin is closed: a mission run is unattended, and an agent CLI that sees an
    open stdin waits on it forever (`codex exec`: "Reading additional input from stdin").
    """
    argv = [sys.executable, str(ADMIT), "run", "--mem", mem, "--job", job, "--", *command]
    if not capture:
        return subprocess.run(argv, cwd=cwd, stdin=subprocess.DEVNULL).returncode, ""
    process = subprocess.run(argv, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, text=True)
    sys.stdout.write(process.stdout)
    return process.returncode, process.stdout


def stop_session(session_id: str) -> int:
    return subprocess.run(["claude", "stop", session_id]).returncode


def gh_pr(number: int, cwd: Path) -> dict[str, Any]:
    output = subprocess.run(["gh", "pr", "view", str(number), "--json", "state,mergeCommit,headRefName"],
                            cwd=cwd, check=True, capture_output=True, text=True, timeout=60).stdout
    return json.loads(output)


def _terminated(_signum: int, _frame: Any) -> None:
    raise SystemExit(143)


def _auto_configuration(root: Path) -> tuple[str, dict[str, list[str]]]:
    """Load the owner's explicit argv allowlist from pyproject.toml (never a shell string)."""
    path = root / "pyproject.toml"
    if path.is_symlink():
        raise ValueError("project pyproject.toml cannot be a symlink")
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"start --auto requires a valid project pyproject.toml: {exc}") from exc
    config = raw.get("tool", {}).get("harness-agent", {})
    executors = config.get("executors") if isinstance(config, dict) else None
    primary = config.get("primary") if isinstance(config, dict) else None
    if (not isinstance(executors, dict) or not executors or config.get("authority") != "owner"
            or primary not in executors
            or primary not in {"codex", "claude"}):
        raise ValueError("[tool.harness-agent] must declare primary and executor argv entries")
    commands: dict[str, list[str]] = {}
    for name, value in executors.items():
        if name not in {"codex", "claude"} or not isinstance(value, dict):
            raise ValueError("only codex and claude executor tables are supported")
        argv = value.get("argv")
        if (not isinstance(argv, list) or not argv
                or any(not isinstance(part, str) or not part or "\0" in part for part in argv)):
            raise ValueError(f"executor {name} must declare a non-empty argv string list")
        commands[name] = argv
    return primary, commands


def _auto_snapshots(path: Path, root: Path) -> dict[str, Snapshot | None]:
    """Read a bounded normalized snapshot file; malformed entries remain unknown."""
    try:
        candidate = path if path.is_absolute() else root / path
        resolved = candidate.resolve(strict=True)
        if not resolved.is_relative_to(root.resolve()) or candidate.is_symlink() or not resolved.is_file():
            return {}
        if resolved.stat().st_size > 1_000_000:
            return {}
        data = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, RuntimeError):
        return {}
    if (not isinstance(data, dict) or type(data.get("format_version")) is not int
            or data.get("format_version") != 1):
        return {}
    result: dict[str, Snapshot | None] = {}
    for name in ("codex", "claude"):
        item = data.get(name)
        if item is None:
            result[name] = None
            continue
        try:
            observed = datetime.fromisoformat(item["observed_at"].replace("Z", "+00:00"))
            windows = [Window(window["remaining"], window["duration_s"],
                              datetime.fromisoformat(window["resets_at"].replace("Z", "+00:00")))
                       for window in item["windows"]]
            result[name] = Snapshot(observed, windows, item.get("status", "allowed"),
                                    item.get("limit_reached", False))
        except (KeyError, TypeError, ValueError, AttributeError):
            result[name] = None
    return result


def _emit(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))


def _start(args: argparse.Namespace, ledger: Ledger, *, runner, stopper,
           watcher_factory: Callable[[Path], Watcher]) -> int:
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    try:
        execution_cwd = (args.cwd or Path.cwd()).expanduser().resolve(strict=True)
        if not execution_cwd.is_dir():
            raise ValueError("not a directory")
    except (OSError, RuntimeError, ValueError) as exc:
        raise SystemExit(f"harness-agent start: invalid --cwd: {exc}") from exc
    quota_decision = None
    batch_plan = None
    if args.auto and args.agent:
        raise SystemExit("harness-agent start: --auto and --agent are exclusive")
    if args.auto:
        prompt = " ".join(command).strip()
        if not prompt:
            raise SystemExit("harness-agent start --auto: provide a prompt after --")
        try:
            primary, commands = _auto_configuration(execution_cwd)
        except ValueError as exc:
            raise SystemExit(f"harness-agent start --auto: {exc}") from exc
        snapshots = _auto_snapshots(args.quota_snapshot, execution_cwd)
        snapshots = {name: snapshot for name, snapshot in snapshots.items() if name in commands}
        key = args.selection_key or f"mission:{args.mission}"
        if len(key) > 160 or not re.fullmatch(r"[A-Za-z0-9._:/-]{1,160}", key):
            raise SystemExit("harness-agent start --auto: --selection-key must be a non-sensitive stable ID")
        snapshots.setdefault(primary, None)
        quota_decision = select_quota(snapshots, primary=primary, selection_key=key,
                                      now=datetime.now().astimezone(), max_age_s=args.quota_max_age)
        command = commands[quota_decision.executor] + [prompt] if quota_decision.executor else []
    elif args.agent:
        prompt = " ".join(command).strip()
        if not args.worktree or not args.output:
            raise SystemExit("harness-agent start --agent: --worktree and --output are required")
        from .agent_profiles import plan as profile_plan
        try:
            batch_plan = profile_plan(args.agent, args.profile, worktree=args.worktree,
                                      ledger=ledger.path, output=args.output.resolve(),
                                      prompt=prompt, network=args.network)
        except (ValueError, subprocess.CalledProcessError) as exc:
            raise SystemExit(f"harness-agent start --agent: {exc}") from exc
        for gap in batch_plan.unenforced:
            print(f"harness-agent: profile {args.profile} not enforced by {args.agent}: {gap}", file=sys.stderr)
        command = batch_plan.argv
    elif not command:
        raise SystemExit("harness-agent start: missing command after --")
    background = _is_background_claude(command)
    if background and args.report is None:
        raise SystemExit("harness-agent start: claude --bg returns at once; --report is required to know the end")
    worktree = args.worktree.resolve() if args.worktree else None
    base = worktree or Path.cwd()
    project = args.project or project_identity(base)
    branch = _git(worktree, "symbolic-ref", "--quiet", "--short", "HEAD") if worktree else None
    holder = args.holder or branch or f"mission-{args.mission}"
    targets = [("path", _claim_path(text, worktree)) for text in args.claim]
    targets += [("branch", name) for name in args.claim_branch]
    if branch and ("branch", branch) not in targets:
        targets.append(("branch", branch))
    if not targets:
        raise SystemExit("harness-agent start: at least one --claim, --claim-branch or --worktree branch is required")
    from .claim_guard import claim_scope_refusal

    refusal = claim_scope_refusal(ledger.path, project, args.mission, holder)
    if refusal:
        raise SystemExit(f"harness-agent start: {refusal}")
    release_on = args.release_on or ("merge" if worktree else "exit")
    deadline = time.monotonic() + args.wait_claims
    while True:
        try:
            held = ledger.acquire_claims(project_root=project, mission_id=args.mission, holder=holder,
                                         targets=targets, wait=args.wait_claims > 0)
            break
        except ClaimConflictError as exc:
            remaining = deadline - time.monotonic()
            woken = None
            if remaining > 0:
                woken = wait_for_mission(ledger, args.mission, timeout=remaining, since=time.time() - 1,
                                         types=frozenset({"woken"}), watcher_factory=watcher_factory)
            if woken is None:
                _emit({"refused": str(exc), "conflicts": exc.conflicts, "mission_id": args.mission})
                return EXIT_REFUSED
        except ValueError as exc:
            _emit({"refused": str(exc), "mission_id": args.mission})
            return 2
    run_id = uuid4().hex
    outcome, returncode, session_id, report = "failed", EXIT_FAILED, args.session_id, None
    previous = signal.signal(signal.SIGTERM, _terminated)
    try:
        if quota_decision is not None and quota_decision.executor is None:
            returncode = EXIT_FAILED
        else:
            runner_args = {"mem": args.mem, "job": args.job or f"mission-{args.mission}",
                           "capture": background and session_id is None}
            if args.cwd is not None:
                runner_args["cwd"] = execution_cwd
            if batch_plan is not None and batch_plan.stdout_to is not None:
                runner_args["capture"] = True
            returncode, output = runner(command, **runner_args)
            if batch_plan is not None and batch_plan.stdout_to is not None:
                batch_plan.stdout_to.write_text(output, encoding="utf-8")
            if background:
                if session_id is None:
                    found = _SESSION.search(output)
                    session_id = found.group(1) if found else None
            if args.report is not None and returncode == 0:
                report_path = args.report if args.report.is_absolute() else execution_cwd / args.report
                report = wait_for_report(report_path, timeout=args.report_timeout, watcher_factory=watcher_factory)
                if background and report is not None and session_id is not None:
                    stopper(session_id)
                if report is None:
                    returncode = EXIT_TIMEOUT
            if report is not None:
                outcome = "completed" if returncode == 0 and report in COMPLETED_STATUSES else "failed"
            else:
                outcome = "completed" if returncode == 0 and args.report is None and not background else "failed"
    except (KeyboardInterrupt, SystemExit) as exc:
        returncode = exc.code if isinstance(exc, SystemExit) and isinstance(exc.code, int) else 130
    finally:
        signal.signal(signal.SIGTERM, previous)
        checkpoint: dict[str, Any] = {"stage": "agent", "writer": "agent_run", "status": outcome, "holder": holder,
                                      "exit_code": max(-255, min(255, returncode)),
                                      "claim_ids": [claim["claim_id"] for claim in held["claims"]]}
        if quota_decision is not None:
            checkpoint["quota_selection"] = {"executor": quota_decision.executor,
                                              "reason": quota_decision.reason,
                                              "weights": dict(quota_decision.weights),
                                              "selection_key": key}
        if worktree is not None:
            checkpoint["worktree"] = str(worktree)
        if branch:
            checkpoint["branch"] = branch
        if session_id:
            checkpoint["session_id"] = session_id
        if report is None and args.report is not None and returncode == EXIT_TIMEOUT:
            checkpoint["error_type"] = "ReportTimeout"
        ledger.record_mission_event(job_id=None, source_sha=None, mission_id=args.mission,
                                    event_id=_derived_event_id("run", run_id, outcome),
                                    event_type=outcome, checkpoint=checkpoint)
        released = None
        if release_on == "exit":
            released = ledger.release_claims(mission_id=args.mission, project_root=project, holder=holder,
                                             reason=outcome, released_by=holder)
    _emit({"mission_id": args.mission, "outcome": outcome, "exit_code": returncode, "report_status": report,
           "session_id": session_id, "quota_selection": (checkpoint.get("quota_selection")
                                                            if quota_decision is not None else None),
           "claims_released": bool(released and released["released"]),
           "woken": released["woken"] if released else []})
    if outcome == "failed" and returncode == 0:
        return EXIT_FAILED
    return returncode


def _release(args: argparse.Namespace, ledger: Ledger, *, pr_reader) -> int:
    try:
        if args.merged_pr is not None:
            from .ledger import mission_branches

            branches = sorted(mission_branches(ledger.claims(mission_id=args.mission), args.mission))
            if not branches:
                released = [c for c in ledger.claims(mission_id=args.mission, active_only=False)
                            if c["kind"] == "branch" and c["released_at"] is not None]
                if released:  # the gate already released it on merge: a replay, not a refusal
                    _emit({"mission_id": args.mission, "replayed": True,
                           "released_reason": released[-1]["release_reason"]})
                    return 0
                raise ClaimAuthorityError("mission holds no branch claim to bind the merged PR")
            pr = pr_reader(args.merged_pr, args.repo.resolve())
            merge_sha = (pr.get("mergeCommit") or {}).get("oid")
            if pr.get("state") != "MERGED" or pr.get("headRefName") not in branches:
                raise ClaimAuthorityError(f"PR #{args.merged_pr} is not a merge of the mission's branch")
            result = ledger.release_claims(mission_id=args.mission, reason="merged", released_by=args.by,
                                           pr_number=args.merged_pr, merge_sha=merge_sha)
        elif args.discard:
            result = ledger.release_claims(mission_id=args.mission, reason="discarded", released_by=args.by,
                                           owner_discard=True)
        else:
            result = ledger.release_claims(mission_id=args.mission, reason=args.reason, released_by=args.by,
                                           holder=args.holder)
    except (ClaimAuthorityError, ValueError, OSError, subprocess.SubprocessError) as exc:
        _emit({"refused": str(exc), "mission_id": args.mission})
        return 2
    _emit(result)
    return 0


def wait_exit_code(event: dict[str, Any] | None) -> int:
    if event is None:
        return EXIT_TIMEOUT
    return EXIT_FAILED if event["event_type"] == "failed" else 0


def main(argv: Sequence[str] | None = None, *, runner=admitted_runner, stopper=stop_session,
         pr_reader=gh_pr, watcher_factory: Callable[[Path], Watcher] = watch) -> int:
    parser = argparse.ArgumentParser(prog="harness-agent", description=__doc__.splitlines()[0])
    parser.add_argument("--ledger", type=Path, help="ledger file (default $HARNESS_LEDGER, else the "
                        "canonical checkout's .sober/update-vanguard.sqlite3)")
    sub = parser.add_subparsers(dest="action", required=True)
    start = sub.add_parser("start", help="take claims, run admitted, record the outcome")
    start.add_argument("--mission", type=int, required=True)
    start.add_argument("--worktree", type=Path, help="the mission's worktree; its branch is claimed too")
    start.add_argument("--claim", action="append", default=[], metavar="PATH")
    start.add_argument("--claim-branch", action="append", default=[], metavar="BRANCH")
    start.add_argument("--holder", help="owner identity (default: worktree branch, else mission-ID)")
    start.add_argument("--project", help="claim space (default: origin identity of the worktree/cwd)")
    start.add_argument("--mem", default="256M", help="harness-admit memory budget (default 256M)")
    start.add_argument("--job", help="harness-admit job name (default mission-ID)")
    start.add_argument("--report", type=Path, help="report whose first line 'STATUS: X' ends the run")
    start.add_argument("--cwd", type=Path, help="execution directory (default: current directory)")
    start.add_argument("--auto", action="store_true", help="select from the project executor allowlist by quota")
    start.add_argument("--quota-snapshot", type=Path, default=Path(".harness/quota.json"),
                       help="normalized snapshot JSON relative to --cwd (default .harness/quota.json)")
    start.add_argument("--selection-key", help="stable non-sensitive key (default mission ID)")
    start.add_argument("--quota-max-age", type=float, default=300.0)
    start.add_argument("--report-timeout", type=float, default=6 * 3600)
    start.add_argument("--session-id", help="claude --bg session to stop (default: parsed from its output)")
    start.add_argument("--release-on", choices=("exit", "merge"),
                       help="exit: release when the run ends; merge: hold until merge or discard "
                            "(default: merge with --worktree, else exit)")
    start.add_argument("--wait-claims", type=float, default=0.0,
                       help="seconds to wait (woken by the release) when a claim is held")
    start.add_argument("--agent", choices=("codex", "claude"),
                       help="build the command from the harness run profile instead of a raw argv; "
                            "the text after -- is the prompt")
    start.add_argument("--profile", default="batch", choices=("batch",),
                       help="harness run profile for --agent (default batch)")
    start.add_argument("--output", type=Path, help="with --agent: file for the agent's final message")
    start.add_argument("--network", action="store_true",
                       help="with --agent: allow network inside the sandbox (off by default)")
    start.add_argument("command", nargs=argparse.REMAINDER)
    wait = sub.add_parser("wait", help="block until the mission's terminal or woken event")
    wait.add_argument("--mission", type=int, required=True)
    wait.add_argument("--timeout", type=float)
    wait.add_argument("--since", type=float, default=0.0, help="ignore events at or before this epoch time")
    release = sub.add_parser("release", help="release a mission's claims (never touches worktrees)")
    release.add_argument("--mission", type=int, required=True)
    release.add_argument("--by", required=True, help="who releases (recorded)")
    mode = release.add_mutually_exclusive_group(required=True)
    mode.add_argument("--reason", choices=("completed", "failed"), help="holder release; needs --holder")
    mode.add_argument("--merged-pr", type=int, help="verify the PR merged the mission's branch (gh), then release")
    mode.add_argument("--discard", action="store_true", help="explicit owner discard of the candidate")
    release.add_argument("--holder")
    release.add_argument("--repo", type=Path, default=Path.cwd(), help="checkout used by gh for --merged-pr")
    mission_cmd = sub.add_parser("mission", help="create a durable mission record")
    mission_sub = mission_cmd.add_subparsers(dest="mission_action", required=True)
    mission_new = mission_sub.add_parser("new", help="allocate the next mission ID and record its title")
    mission_new.add_argument("--title", required=True)
    mission_open = mission_sub.add_parser(
        "open", help="create the mission, its worktree on a new branch and its claims (ownership from birth)")
    mission_open.add_argument("--title", required=True)
    mission_open.add_argument("--branch", required=True, help="new branch name (never a reused one)")
    mission_open.add_argument("--path", action="append", default=[], help="repository-relative path to claim")
    mission_open.add_argument("--repo", type=Path, default=Path.cwd())
    mission_open.add_argument("--base", default="origin/main")
    mission_open.add_argument("--worktree-root", type=Path, default=None)
    mission_open.add_argument("--checkout", type=Path, default=None,
                              help="existing clone of the same remote where the work happens (no worktree)")
    for name, help_text in (("state", "print the mission's lifecycle state (a fold of its journal)"),
                            ("park", "keep the mission's work until its resume condition fires; never collected while parked"),
                            ("unpark", "end a park; terminal missions become collectable again"),
                            ("discard", "owner discards the mission's work: collectable after archive")):
        lifecycle = mission_sub.add_parser(name, help=help_text)
        lifecycle.add_argument("mission_id", type=int)
        if name == "park":
            lifecycle.add_argument("--reason", required=True, help="why the work stops (recorded)")
            lifecycle.add_argument("--resume-on", required=True,
                                   help="what resumes it: pr:N (leaves OPEN), claim:N (released) or date:YYYY-MM-DD")
    claims_cmd = sub.add_parser("claims", help="owner releases no holder or gate can make, with a recorded proof")
    claims_sub = claims_cmd.add_subparsers(dest="claims_action", required=True)
    orphan = claims_sub.add_parser("release-orphan", help="release claims of a mission this ledger does not hold")
    orphan.add_argument("claim_ids", type=int, nargs="+")
    closed = claims_sub.add_parser("release-closed", help="close a mission whose PR closed unmerged and release it")
    closed.add_argument("--mission", type=int, required=True)
    closed.add_argument("--pr", type=int, required=True)
    for owner_cmd in (orphan, closed):
        owner_cmd.add_argument("--by", required=True, help="the owner releasing")
        owner_cmd.add_argument("--repo", type=Path, default=Path.cwd())
    checkpoint_cmd = mission_sub.add_parser(
        "checkpoint", help="the claim holder records its progress (closed stages, harness error types)")
    checkpoint_cmd.add_argument("mission_id", type=int)
    checkpoint_cmd.add_argument("--by", required=True, help="the claim holder writing (recorded)")
    checkpoint_cmd.add_argument("--stage", required=True, choices=WORKER_STAGES)
    checkpoint_cmd.add_argument("--next-step", required=True, choices=WORKER_NEXT_STEPS)
    checkpoint_cmd.add_argument("--error-type", choices=sorted(FAILURE_CLASSIFICATION),
                                help="a failure the harness produced; its classification is looked up")
    checkpoint_cmd.add_argument("--head-sha")
    checkpoint_cmd.add_argument("--pr", type=int)
    checkpoint_cmd.add_argument("--file", action="append", default=[], help="repository-relative path")
    merged = mission_sub.add_parser("merged", help="owner records the merged PR of a mission that holds no claims")
    merged.add_argument("mission_id", type=int)
    merged.add_argument("--pr", type=int, required=True)
    merged.add_argument("--by", required=True, help="the owner recording")
    merged.add_argument("--repo", type=Path, default=Path.cwd())
    gate = sub.add_parser("gate", help="run the declared project adapter for a pushed PR head")
    gate.add_argument("--pr", type=int, required=True)
    gate.add_argument("--repo", type=Path, default=Path.cwd())
    gate.add_argument("--report", type=Path)
    gate.add_argument("--mission", type=int)
    ledger_cmd = sub.add_parser("ledger", help="bind or show the one ledger every clone of a remote uses")
    ledger_sub = ledger_cmd.add_subparsers(dest="ledger_action", required=True)
    ledger_bind = ledger_sub.add_parser("bind", help="bind this repository's identity to --ledger")
    ledger_bind.add_argument("--repo", type=Path, default=Path.cwd())
    ledger_bind.add_argument("--replace", action="store_true", help="rebind an identity bound elsewhere")
    ledger_show = ledger_sub.add_parser("show", help="identity, bound ledger and resolved ledger")
    ledger_show.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    base = (getattr(args, "worktree", None) or Path.cwd())
    if args.action == "ledger":
        identity = project_identity(args.repo)
        if args.ledger_action == "bind":
            if args.ledger is None:
                parser.error("ledger bind requires the global --ledger PATH")
            _emit(bind_ledger(identity, args.ledger, replace=args.replace))
            return 0
        bound = bound_ledger(identity)
        _emit({"identity": identity, "bound": str(bound) if bound else None,
               "resolved": str(resolve_ledger(None, args.repo)), "registry": str(ledger_registry_path())})
        return 0
    if args.action == "claims":
        from . import owner_release
        from .worktree_gc import release_branch_resources
        from .worktrees import NotMeasured, repo_root

        root = repo_root(args.repo)
        ledger = Ledger(resolve_ledger(args.ledger, root))
        try:
            result = (owner_release.release_orphan(ledger, root, args.claim_ids, by=args.by)
                      if args.claims_action == "release-orphan"
                      else owner_release.release_closed(ledger, root, args.mission, args.pr, by=args.by))
        except (ClaimAuthorityError, NotMeasured, ValueError) as exc:
            _emit({"refused": str(exc)})
            return 2
        proof = result["proof"]
        branches = [item["branch"] for item in proof.get("branches", [])] or [proof["branch"]]
        # The `Drop` of the release: worktrees that now have no claim are assessed and archived now.
        result["collected"] = {branch: [w["worktree"] for w in release_branch_resources(
            root, ledger.path, branch)["worktrees"] if w.get("removed")] for branch in branches}
        _emit(result)
        return 0
    if args.action == "mission" and args.mission_action == "merged":
        from . import mission_lifecycle, owner_release
        from .worktrees import NotMeasured, repo_root

        root = repo_root(args.repo)
        ledger = Ledger(resolve_ledger(args.ledger, root))
        try:
            _emit(owner_release.record_merged(ledger, root, args.mission_id, args.pr, by=args.by))
        except (ClaimAuthorityError, NotMeasured, ValueError, mission_lifecycle.InvalidTransition) as exc:
            _emit({"refused": str(exc)})
            return 2
        return 0
    if args.action == "mission" and args.mission_action == "checkpoint":
        ledger = Ledger(resolve_ledger(args.ledger, Path(base)))
        try:
            _emit(record_worker_checkpoint(ledger, args.mission_id, by=args.by, stage=args.stage,
                                           next_step=args.next_step, error_type=args.error_type,
                                           head_sha=args.head_sha, pr_number=args.pr, files=args.file))
        except (ClaimAuthorityError, ValueError) as exc:
            _emit({"refused": str(exc)})
            return 2
        return 0
    if args.action == "mission" and args.mission_action == "open":
        from . import mission_lifecycle
        from .worktrees import repo_root

        root = repo_root(args.repo)
        ledger = Ledger(resolve_ledger(args.ledger, root))
        try:
            opened = mission_lifecycle.open_mission(
                ledger, root, title=args.title.strip(), branch=args.branch, paths=args.path,
                base=args.base, worktree_root=args.worktree_root, checkout=args.checkout)
        except (ValueError, ClaimConflictError) as exc:
            print(f"harness-agent: {exc}", file=sys.stderr)
            return 2
        _emit(opened)
        return 0
    if args.action == "mission" and args.mission_action != "new":
        from . import mission_lifecycle

        ledger = Ledger(resolve_ledger(args.ledger, Path(base)))
        stage = {"park": "parked", "unpark": "unparked", "discard": "discarded"}.get(args.mission_action)
        try:
            if stage == "parked":
                current = mission_lifecycle.park(ledger, args.mission_id, reason=args.reason,
                                                 resume_on=args.resume_on)
            else:
                current = (mission_lifecycle.record(ledger, args.mission_id, stage) if stage
                           else mission_lifecycle.state(ledger, args.mission_id))
        except (mission_lifecycle.InvalidTransition, ValueError) as exc:
            print(f"harness-agent: {exc}", file=sys.stderr)
            return 2
        result = current.as_dict()
        if stage == "discarded":
            # The `Drop` of a discard: the mission's worktrees go now, archived, not at the next sweep.
            from .worktree_gc import release_branch_resources
            from .worktrees import repo_root

            root = repo_root(Path(base))
            branches = sorted({c["target"] for c in ledger.claims(project_root=project_identity(root),
                                                                   mission_id=args.mission_id,
                                                                   active_only=False)
                               if c["kind"] == "branch"})
            result["released"] = {branch: [w["worktree"] for w in release_branch_resources(
                root, ledger.path, branch)["worktrees"] if w.get("removed")] for branch in branches}
        _emit(result)
        return 0
    if args.action == "mission":
        ledger = Ledger(resolve_ledger(args.ledger, Path(base)))
        title = args.title.strip()
        if not title or len(title) > 240:
            parser.error("--title deve ter entre 1 e 240 caracteres")
        try:
            mission_id = ledger.create_mission(title)
        except ValueError as exc:
            parser.error(str(exc))
        _emit({"mission_id": mission_id, "title": title})
        return 0
    if args.action == "gate":
        if args.pr < 1 or (args.mission is not None and args.mission < 1):
            parser.error("PR e mission devem ser inteiros positivos")
        # The ledger is resolved with or without --mission: a merge releases every claim
        # held on the PR's branch, and an unresolved ledger left them active forever.
        try:
            ledger = Ledger(resolve_ledger(args.ledger, args.repo))
        except SystemExit:
            if args.mission is not None:
                raise
            ledger = None  # project not adopted: nothing holds claims to release
        return run_gate(pr=args.pr, repo=args.repo.resolve(), report=args.report,
                        mission=args.mission, ledger=ledger,
                        project=project_identity(args.repo) if ledger is not None else None)
    ledger = Ledger(resolve_ledger(args.ledger, Path(base)))
    if args.action == "start":
        return _start(args, ledger, runner=runner, stopper=stopper, watcher_factory=watcher_factory)
    if args.action == "release":
        return _release(args, ledger, pr_reader=pr_reader)
    event = wait_for_mission(ledger, args.mission, timeout=args.timeout, since=args.since,
                             watcher_factory=watcher_factory)
    _emit(event if event is not None else {"mission_id": args.mission, "event_type": "timeout"})
    return wait_exit_code(event)


if __name__ == "__main__":
    raise SystemExit(main())
