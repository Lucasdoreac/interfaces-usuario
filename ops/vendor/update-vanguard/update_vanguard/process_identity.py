"""Process identity that survives PID reuse, on Linux (/proc) and macOS (libproc).

One source for every caller that records "who owns this" and later asks "is that
owner still alive" (the canonical code gate today; release leases next). The
answer never guesses: ``owner_gone`` returns a reason only when the kernel proves
the owner is gone, and None whenever liveness cannot be decided here.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from typing import Any

# macOS has no PID namespaces; one constant keeps a Linux owner (e.g. a container)
# from ever being compared with a host process, in either direction.
DARWIN_PID_NAMESPACE = "darwin"
_PROC_PIDTBSDINFO = 3
_PROC_BSDINFO_SIZE = 136  # sizeof(struct proc_bsdinfo): pbi_pid at 12, start sec/usec at 120/128


class LivenessUndecidable(Exception):
    """The kernel refused to say whether a process exists; never treat it as gone."""


def _is_darwin() -> bool:
    return sys.platform == "darwin"


def boot_id() -> str | None:
    if _is_darwin():
        try:
            completed = subprocess.run(["sysctl", "-n", "kern.bootsessionuuid"],
                                       stdin=subprocess.DEVNULL, capture_output=True,
                                       text=True, timeout=5, check=False)
        except (OSError, subprocess.SubprocessError):
            return None
        value = completed.stdout.strip()
        return value if completed.returncode == 0 and value else None
    try:
        return Path("/proc/sys/kernel/random/boot_id").read_text().strip() or None
    except OSError:
        return None


def _darwin_starttime(pid: int) -> int | None:
    """Start time in microseconds from proc_pidinfo; None only when the PID is gone (ESRCH)."""
    import ctypes
    import errno
    import struct

    if pid <= 0:
        return None
    try:
        libproc = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
    except OSError as exc:
        raise LivenessUndecidable("libproc is unavailable") from exc
    buffer = ctypes.create_string_buffer(_PROC_BSDINFO_SIZE)
    ctypes.set_errno(0)
    size = libproc.proc_pidinfo(pid, _PROC_PIDTBSDINFO, ctypes.c_uint64(0), buffer, _PROC_BSDINFO_SIZE)
    if size != _PROC_BSDINFO_SIZE:
        if size == 0 and ctypes.get_errno() == errno.ESRCH:
            return None
        raise LivenessUndecidable(f"proc_pidinfo failed (errno {ctypes.get_errno()})")
    reported_pid, = struct.unpack_from("I", buffer.raw, 12)
    if reported_pid != pid:
        raise LivenessUndecidable("proc_pidinfo returned another process")
    seconds, micros = struct.unpack_from("QQ", buffer.raw, 120)
    return seconds * 1_000_000 + micros


def process_starttime(pid: int) -> int | None:
    """Kernel start time of ``pid``, or None if it is gone; raises when undecidable."""
    if _is_darwin():
        return _darwin_starttime(pid)
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
    except OSError:
        return None
    try:
        return int(stat[stat.rindex(")") + 2:].split()[19])  # field 22
    except (ValueError, IndexError):
        return None


def pid_namespace() -> str | None:
    if _is_darwin():
        return DARWIN_PID_NAMESPACE
    try:
        return os.readlink("/proc/self/ns/pid")
    except OSError:
        return None


def process_identity(pid: int | None = None) -> dict[str, Any] | None:
    """Boot, PID namespace, PID and kernel start time; None when any is unknowable here."""
    pid = os.getpid() if pid is None else pid
    try:
        starttime = process_starttime(pid)
    except LivenessUndecidable:
        return None
    boot, namespace = boot_id(), pid_namespace()
    if boot is None or starttime is None or namespace is None:
        return None
    return {"boot_id": boot, "pid_ns": namespace, "pid": pid, "starttime": starttime}


def owner_gone(owner: dict[str, Any]) -> str | None:
    """Why ``owner`` is provably dead, or None (alive, or not decidable from this process)."""
    boot = boot_id()
    if boot is None or not isinstance(owner.get("pid"), int):
        return None
    namespace = pid_namespace()
    if owner.get("pid_ns") != namespace:
        # Another PID namespace: its PIDs are invisible here. Only two Linux namespaces
        # share one kernel boot_id, so only then does a different boot prove the owner died.
        linux_pair = DARWIN_PID_NAMESPACE not in (owner.get("pid_ns"), namespace)
        return "owner ran in a previous boot" if linux_pair and owner.get("boot_id") != boot else None
    if owner.get("boot_id") != boot:
        return "owner ran in a previous boot"
    try:
        starttime = process_starttime(owner["pid"])
    except LivenessUndecidable:
        return None
    if starttime is None:
        return "owner process no longer exists"
    if starttime != owner.get("starttime"):
        return "owner PID was reused by another process"
    return None
