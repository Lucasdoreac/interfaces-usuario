"""PARADIGMA: single host-memory admission point for agent workloads.

Admission is a decision against the whole host, not a reservation the kernel
enforces. It answers one question under a cross-process lock: does
``MemAvailable - outstanding admitted budgets - mem_bytes`` still leave
``reserve_bytes`` for everything else? Missing evidence never admits. The
kernel cap is a separate layer: on Linux, ``harness-admit run`` places the
admitted command in a transient scope under ``agents.slice`` with
``MemoryMax`` equal to the admitted budget, so a workload that lies about its
size dies inside its own cgroup instead of driving the host into global OOM.

Each admission holds a lease file (flock) for its lifetime. Later admissions
subtract the budgets of live leases from ``MemAvailable``. This double counts
memory a running job has already touched, which errs toward refusal; a
crashed holder's lease is reclaimed because its lock is gone.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass, field
import errno
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import sys
import time
from typing import Any, Callable, Iterator, Protocol, Sequence
from uuid import uuid4

STATE_DIRNAME = "personal-dev-harness-admission"
SLICE = "agents.slice"
DEFAULT_RESERVE_BYTES = 1024**3
DARWIN_RESERVE_BYTES = DEFAULT_RESERVE_BYTES
DARWIN_MAX_ADMITTED_BYTES = 2 * 1024**3
DARWIN_WATCH_INTERVAL_SECONDS = 0.25
MEMORY_HIGH_RATIO = 0.85
EXIT_REFUSED = 75  # EX_TEMPFAIL: memory below the floor; retry later.
EXIT_UNAVAILABLE = 69  # EX_UNAVAILABLE: no evidence or no cgroup adapter.
_JOB = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_SIZE = re.compile(r"^(\d+(?:\.\d+)?)([KMGT]?)i?B?$", re.IGNORECASE)
_UNITS = {"": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
_POLL_SECONDS = 5.0


class AdmissionRefused(RuntimeError):
    """The host cannot take this workload now; nothing was started."""

    def __init__(self, reason: str, *, job: str, available_bytes: int | None = None,
                 required_bytes: int | None = None):
        super().__init__(reason)
        self.reason = reason
        self.job = job
        self.available_bytes = available_bytes
        self.required_bytes = required_bytes


class ResourceEvidenceUnavailable(AdmissionRefused):
    """Host memory could not be measured, so admission fails closed."""


class MissionRecorder(Protocol):
    def record(self, event_type: str, checkpoint: dict[str, Any]) -> None: ...


@dataclass(frozen=True)
class BridgeMissionRecorder:
    """Records admission transitions as canonical mission events via the update bridge."""

    root: Path
    actor_id: str
    mission_id: int
    job_id: str
    source_sha: str

    def record(self, event_type: str, checkpoint: dict[str, Any]) -> None:
        from .bridge import UpdateBridge

        UpdateBridge(self.root).submit_mission_event(
            request_id=uuid4().hex, actor_id=self.actor_id, mission_id=self.mission_id,
            job_id=self.job_id, source_sha=self.source_sha,
            event_type=event_type, checkpoint=checkpoint,
        )


@dataclass
class Admission:
    """A granted budget; the lease stays live until :meth:`release`."""

    job: str
    mem_bytes: int
    reserve_bytes: int
    available_bytes: int
    lease_path: Path
    _descriptor: int | None = field(default=None, repr=False)

    def release(self) -> None:
        if self._descriptor is None:
            return
        try:
            self.lease_path.unlink(missing_ok=True)
        finally:
            os.close(self._descriptor)
            self._descriptor = None

    def __enter__(self) -> "Admission":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.release()


def parse_size(text: str) -> int:
    """Parse ``300M``/``2G``/``1.5G``/``1048576`` as binary bytes."""
    match = _SIZE.fullmatch(text.strip()) if isinstance(text, str) else None
    if match is None:
        raise ValueError(f"invalid size: {text!r}")
    value = int(float(match.group(1)) * _UNITS[match.group(2).upper()])
    if value <= 0:
        raise ValueError(f"size must be positive: {text!r}")
    return value


def _parse_memavailable_bytes(meminfo: str) -> int:
    """Return MemAvailable in bytes; anything but ``<digits> kB`` is not evidence."""
    for line in meminfo.splitlines():
        name, separator, value = line.partition(":")
        if name != "MemAvailable" or not separator:
            continue
        parts = value.split()
        if len(parts) == 2 and parts[0].isdigit() and parts[1] == "kB":
            return int(parts[0]) * 1024
        break
    raise ValueError("invalid or missing MemAvailable")


def _parse_vm_stat_available_bytes(vm_stat: str) -> int:
    """macOS approximation of MemAvailable: free + inactive + speculative pages."""
    page = re.search(r"page size of (\d+) bytes", vm_stat)
    counts = dict(re.findall(r"^Pages (free|inactive|speculative):\s+(\d+)\.$", vm_stat, re.MULTILINE))
    if page is None or set(counts) != {"free", "inactive", "speculative"}:
        raise ValueError("invalid vm_stat output")
    return sum(int(value) for value in counts.values()) * int(page.group(1))


def _host_mem_available_bytes(job: str = "host") -> int:
    """Measure available host RAM; missing evidence cannot admit work."""
    try:
        if sys.platform == "darwin":
            output = subprocess.run(["vm_stat"], capture_output=True, text=True,
                                    check=True, timeout=10).stdout
            return _parse_vm_stat_available_bytes(output)
        return _parse_memavailable_bytes(Path("/proc/meminfo").read_text(encoding="ascii"))
    except (OSError, UnicodeError, ValueError, subprocess.SubprocessError) as exc:
        raise ResourceEvidenceUnavailable(
            f"resource_unavailable: cannot read host available memory ({type(exc).__name__})", job=job,
        ) from exc


def _darwin_group_rss_bytes(pgid: int) -> int | None:
    """Group RSS, or None when no live member remains (zero RSS is still live).

    Sample membership and RSS together, including reparented descendants.
    Zombies have exited and cannot consume the admission budget.
    """
    output = subprocess.run(["ps", "-axo", "pgid=,rss=,stat="], capture_output=True, text=True,
                            check=True, timeout=10).stdout
    if not output.strip():
        raise ValueError("empty ps process-group RSS output")
    total_kib = 0
    live = False
    for line in output.splitlines():
        fields = line.split()
        if not fields:
            continue
        if len(fields) != 3:
            raise ValueError("invalid ps process-group RSS output")
        try:
            group, rss = int(fields[0]), int(fields[1])
        except ValueError as exc:
            raise ValueError("invalid ps process-group RSS output") from exc
        if group < 0 or rss < 0:
            raise ValueError("invalid ps process-group RSS output")
        if group == pgid and not fields[2].startswith("Z"):
            live = True
            total_kib += rss
    return total_kib * 1024 if live else None


def _signal_darwin_group(pgid: int, sig: int) -> bool:
    """Signal the whole group; EPERM still proves members exist, so fail closed."""
    try:
        os.killpg(pgid, sig)
    except ProcessLookupError:
        return False
    except PermissionError:
        # The group exists but this process cannot signal it. In particular,
        # signal 0 must not turn EPERM into proof of exit and release its lease.
        return True
    return True


def _run_darwin_watched(command: Sequence[str], mem_bytes: int) -> int:
    """Run an isolated process group and stop it when observed RSS exceeds budget.

    macOS has no per-process-group hard memory limit. This supervisor is a
    bounded-overshoot guard, not kernel enforcement; children that deliberately
    detach with setsid can escape the group and are outside this guarantee.
    """
    process: subprocess.Popen | None = None
    pgid: int | None = None
    pending: list[int] = []

    def forward(sig: int, _frame: object) -> None:
        if pgid is None:
            pending.append(sig)
        else:
            _signal_darwin_group(pgid, sig)

    previous = {}
    try:
        # Caught handlers become SIG_DFL on exec, whereas SIG_IGN survives it.
        # Install before spawning, even if our caller inherited ignored signals.
        # start_new_session isolates the child from terminal signals; forward
        # both explicitly and queue signals received during Popen.
        for sig in (signal.SIGINT, signal.SIGTERM):
            previous[sig] = signal.signal(sig, forward)
        process = subprocess.Popen(list(command), start_new_session=True, restore_signals=True)
        pgid = process.pid
        for sig in pending:
            _signal_darwin_group(pgid, sig)

        termination_status: int | None = None
        kill_at: float | None = None
        while True:
            process.poll()  # reap the leader without treating its exit as group exit
            try:
                rss = _darwin_group_rss_bytes(pgid)
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                if termination_status != EXIT_UNAVAILABLE:
                    print(f"harness-admit: Darwin RSS evidence unavailable; terminating pgid={pgid} "
                          f"({type(exc).__name__})", file=sys.stderr)
                termination_status = EXIT_UNAVAILABLE
                # Missing measurement cannot prove group exit. As in the ledger
                # PID probe, signal 0 only treats ProcessLookupError as death.
                rss = 0 if _signal_darwin_group(pgid, 0) else None
            if rss is None:
                returncode = process.wait()
                return termination_status if termination_status is not None else _exit_status(returncode)
            if termination_status is None and rss > mem_bytes:
                print(f"harness-admit: Darwin RSS limit exceeded; terminating pgid={pgid} "
                      f"rss_bytes={rss} limit_bytes={mem_bytes}", file=sys.stderr)
                termination_status = 128 + signal.SIGTERM
            if termination_status is not None:
                if kill_at is None:
                    _signal_darwin_group(pgid, signal.SIGTERM)
                    kill_at = time.monotonic() + 2
                elif time.monotonic() >= kill_at:
                    _signal_darwin_group(pgid, signal.SIGKILL)
                    kill_at = float("inf")
                    if termination_status != EXIT_UNAVAILABLE:
                        termination_status = 128 + signal.SIGKILL
            time.sleep(DARWIN_WATCH_INTERVAL_SECONDS)
    except BaseException:
        if process is not None and pgid is not None:
            _signal_darwin_group(pgid, signal.SIGKILL)
            process.wait()
            # Preserve the lease until cleanup is observed, even after leader exit.
            while _signal_darwin_group(pgid, 0):
                time.sleep(DARWIN_WATCH_INTERVAL_SECONDS)
        raise
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def _runtime_dir() -> str | None:
    """Per-user private directory shared by every process of this user.

    Linux: ``$XDG_RUNTIME_DIR``. macOS has none; its per-user temp dir
    (``getconf DARWIN_USER_TEMP_DIR``, mode 0700) is the same for every process of
    the user whatever ``TMPDIR`` says, so the admission lock stays shared.
    """
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if runtime or sys.platform != "darwin":
        return runtime
    try:
        output = subprocess.run(["getconf", "DARWIN_USER_TEMP_DIR"], capture_output=True,
                                text=True, check=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    return output or None


def _state_dir(lock_dir: Path | None, job: str) -> Path:
    if lock_dir is None:
        runtime = _runtime_dir()
        if not runtime:
            raise ResourceEvidenceUnavailable(
                "resource_unavailable: XDG_RUNTIME_DIR is unset; no shared admission lock", job=job)
        lock_dir = Path(runtime)
    state = lock_dir / STATE_DIRNAME
    if lock_dir.is_symlink() or state.is_symlink():
        raise ResourceEvidenceUnavailable("resource_unavailable: admission state is a symlink", job=job)
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = state.stat(follow_symlinks=False)
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise ResourceEvidenceUnavailable(
            "resource_unavailable: admission state is not private to this user", job=job)
    return state


@contextmanager
def _exclusive(path: Path) -> Iterator[None]:
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)


def _outstanding_bytes(state: Path) -> int:
    """Sum budgets of live leases; reclaim leases whose holder is gone."""
    total = 0
    for lease in state.glob("lease-*.json"):
        try:
            descriptor = os.open(lease, os.O_RDWR | os.O_NOFOLLOW)
        except FileNotFoundError:
            continue
        try:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                if exc.errno not in (errno.EAGAIN, errno.EACCES):
                    raise
                payload = json.loads(os.pread(descriptor, 4096, 0) or b"{}")
                budget = payload.get("mem_bytes")
                # A live lease with an unreadable budget cannot be ignored.
                if type(budget) is not int or budget <= 0:
                    raise ValueError(f"live admission lease has no valid budget: {lease.name}")
                total += budget
            else:
                lease.unlink(missing_ok=True)
        finally:
            os.close(descriptor)
    return total


def admit(job: str, mem_bytes: int, reserve_bytes: int, *, lock_dir: Path | None = None,
          mission_id: int | None = None, recorder: MissionRecorder | None = None,
          wait_seconds: float = 0.0,
          max_total_bytes: int | None = None,
          measure: Callable[[str], int] | None = None,
          clock: Callable[[], float] = time.monotonic,
          sleep: Callable[[float], None] = time.sleep) -> Admission:
    """Grant ``mem_bytes`` to ``job`` only if ``reserve_bytes`` stays free afterwards.

    Raises :class:`AdmissionRefused` (memory below the floor after waiting)
    or :class:`ResourceEvidenceUnavailable` (no measurement; never waited on).
    With ``mission_id``, ``waiting`` and ``claimed`` are recorded through
    ``recorder`` before the caller can start work; a recording failure
    refuses admission rather than running unaudited.
    """
    if not isinstance(job, str) or not _JOB.fullmatch(job):
        raise ValueError("job must match [a-z0-9][a-z0-9._-]{0,63}")
    if type(mem_bytes) is not int or mem_bytes <= 0 or type(reserve_bytes) is not int or reserve_bytes < 0:
        raise ValueError("mem_bytes must be positive and reserve_bytes non-negative integers")
    if mission_id is not None and recorder is None:
        raise ValueError("mission_id requires a mission recorder")
    if max_total_bytes is None and sys.platform == "darwin":
        max_total_bytes = DARWIN_MAX_ADMITTED_BYTES
    if max_total_bytes is not None and (type(max_total_bytes) is not int or max_total_bytes <= 0):
        raise ValueError("max_total_bytes must be a positive integer")
    if max_total_bytes is not None and mem_bytes > max_total_bytes:
        raise AdmissionRefused("resource_unavailable: request exceeds host agent budget", job=job,
                               required_bytes=mem_bytes)
    measure = measure or _host_mem_available_bytes
    state = _state_dir(lock_dir, job)
    deadline = clock() + max(0.0, wait_seconds)
    waited = False
    started = clock()
    while True:
        with _exclusive(state / "admission.lock"):
            try:
                outstanding = _outstanding_bytes(state)
            except (OSError, ValueError) as exc:
                raise ResourceEvidenceUnavailable(
                    f"resource_unavailable: admission leases unreadable ({exc})", job=job) from exc
            available = measure(job) - outstanding
            if available - mem_bytes >= reserve_bytes and (
                    max_total_bytes is None or outstanding + mem_bytes <= max_total_bytes):
                admission = _grant(state, job, mem_bytes, reserve_bytes, available)
                if mission_id is not None:
                    try:
                        recorder.record("claimed", {
                            "stage": "host_admission", "status": "running",
                            "wait_seconds": min(86400, int(clock() - started)),
                        })
                    except BaseException:
                        admission.release()
                        raise
                return admission
        if clock() >= deadline:
            raise AdmissionRefused(
                f"resource_unavailable: {job} not started; available={available // 1024**2} MiB, "
                f"requested={mem_bytes // 1024**2} MiB, reserve={reserve_bytes // 1024**2} MiB",
                job=job, available_bytes=available, required_bytes=mem_bytes + reserve_bytes,
            )
        if mission_id is not None and not waited:
            recorder.record("waiting", {
                "stage": "host_admission", "status": "waiting", "next_step": "wait",
                "classification": "transient",
                "wait_seconds": min(86400, int(max(0.0, deadline - clock()))),
            })
        waited = True
        sleep(min(_POLL_SECONDS, max(0.0, deadline - clock())))


def _grant(state: Path, job: str, mem_bytes: int, reserve_bytes: int, available: int) -> Admission:
    lease = state / f"lease-{uuid4().hex}.json"
    descriptor = os.open(lease, os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        payload = {"job": job, "mem_bytes": mem_bytes, "pid": os.getpid(), "admitted_at": time.time()}
        os.write(descriptor, json.dumps(payload, sort_keys=True).encode("ascii"))
        os.fsync(descriptor)
    except BaseException:
        os.close(descriptor)
        lease.unlink(missing_ok=True)
        raise
    return Admission(job, mem_bytes, reserve_bytes, available, lease, descriptor)


def scope_argv(command: Sequence[str], mem_bytes: int, swap_bytes: int) -> list[str]:
    """Exact ``systemd-run`` invocation that caps ``command`` inside ``agents.slice``.

    MemoryHigh below MemoryMax only helps when the scope may swap: with no
    swap, anonymous memory over ``high`` cannot be reclaimed, so the kernel
    throttles the job for minutes instead of OOM-killing it at ``max``
    (observed on the host: 300M scope stalled 4 min at 290M, oom_kill 0).
    """
    high = int(mem_bytes * MEMORY_HIGH_RATIO) if swap_bytes > 0 else "infinity"
    return [
        "systemd-run", "--user", "--scope", f"--slice={SLICE}",
        "-p", f"MemoryMax={mem_bytes}",
        "-p", f"MemoryHigh={high}",
        "-p", f"MemorySwapMax={swap_bytes}",
        "--", *command,
    ]


def _bridge_recorder(args: argparse.Namespace) -> BridgeMissionRecorder | None:
    if args.mission is None:
        return None
    missing = [flag for flag, value in (("--bridge-root", args.bridge_root), ("--job-id", args.job_id),
                                        ("--source-sha", args.source_sha), ("--actor", args.actor))
               if not value]
    if missing:
        raise SystemExit(f"harness-admit: --mission requires {', '.join(missing)}")
    return BridgeMissionRecorder(Path(args.bridge_root), args.actor, args.mission,
                                 args.job_id, args.source_sha)


def _default_job(command: Sequence[str]) -> str:
    name = re.sub(r"[^a-z0-9._-]+", "-", Path(command[0]).name.lower()).strip("-._")
    return (name or "job")[:64]


def _exit_status(returncode: int) -> int:
    return 128 - returncode if returncode < 0 else returncode


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="harness-admit", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="action", required=True)
    run = sub.add_parser("run", help="admit against host memory, then run capped in agents.slice")
    run.add_argument("--mem", required=True, type=parse_size, help="memory budget, e.g. 2G")
    run.add_argument("--reserve", type=parse_size, default=None,
                     help="memory that must stay available for the host (default 1G)")
    run.add_argument("--swap", type=parse_size, default=None,
                     help="MemorySwapMax for the scope (default 0: admitted work fits in RAM)")
    run.add_argument("--wait", type=float, default=0.0, help="seconds to wait for memory")
    run.add_argument("--job", help="job name for leases and messages (default: command name)")
    run.add_argument("--lock-dir", type=Path, default=None, help="default $XDG_RUNTIME_DIR")
    run.add_argument("--mission", type=int, help="canonical mission id for waiting/claimed events")
    run.add_argument("--bridge-root", help="project root whose update bridge records mission events")
    run.add_argument("--job-id", help="canonical update job id bound to the mission")
    run.add_argument("--source-sha", help="full source SHA bound to the mission")
    run.add_argument("--actor", help="authenticated owner transport id for the bridge")
    run.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("missing command after --")
    swap = 0 if args.swap is None else args.swap
    darwin = sys.platform == "darwin"
    capped = not darwin
    reserve = args.reserve if args.reserve is not None else (
        DARWIN_RESERVE_BYTES if darwin else DEFAULT_RESERVE_BYTES)
    if capped and shutil.which("systemd-run") is None:
        print("harness-admit: systemd-run not found; refusing to run uncapped on Linux", file=sys.stderr)
        return EXIT_UNAVAILABLE
    job = args.job or _default_job(command)
    try:
        admission = admit(job, args.mem, reserve, lock_dir=args.lock_dir,
                          mission_id=args.mission, recorder=_bridge_recorder(args),
                          wait_seconds=args.wait)
    except ResourceEvidenceUnavailable as exc:
        print(f"harness-admit: {exc}", file=sys.stderr)
        return EXIT_UNAVAILABLE
    except AdmissionRefused as exc:
        print(f"harness-admit: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    with admission:
        if capped:
            argv_to_run = scope_argv(command, args.mem, swap)
        else:
            print("harness-admit: macOS RSS supervisor active (250ms sampling; process-group scope; "
                  "not a kernel hard limit)", file=sys.stderr)
            return _run_darwin_watched(command, args.mem)
        process = subprocess.Popen(argv_to_run)
        previous = signal.signal(signal.SIGINT, signal.SIG_IGN)
        try:
            returncode = process.wait()
        finally:
            signal.signal(signal.SIGINT, previous)
    return _exit_status(returncode)


if __name__ == "__main__":
    raise SystemExit(main())
