"""Crash-safe cleanup for explicitly managed agent scratch directories.

Only direct children created by :func:`managed_scratch` are eligible. Git
worktrees, repositories, arbitrary temporary paths and shared caches are never
discovered or removed by this collector.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import math
import os
import shutil
import stat
import tempfile
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

_MARKER = ".personal-dev-harness-scratch.json"
_LEASE = ".personal-dev-harness-lease"
_KINDS = {"agent-run", "test-run", "provider-run"}
_MANAGED_BY = "personal-dev-harness"


def default_scratch_root() -> Path:
    if os.name == "nt":
        raise RuntimeError("Windows scratch collection is not supported by this adapter")
    if Path.home().joinpath("Library").is_dir() and os.uname().sysname == "Darwin":
        return Path.home() / "Library" / "Caches" / _MANAGED_BY / "scratch"
    state_home = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return state_home / _MANAGED_BY / "scratch"


def _safe_root(root: Path, *, create: bool) -> Path:
    root = root.expanduser().absolute()
    if create:
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        info = root.lstat()
    except FileNotFoundError:
        return root
    if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
        raise ValueError("managed scratch root must be a real directory, not a symlink")
    if info.st_uid != os.getuid():
        raise ValueError("managed scratch root must be owned by the current user")
    return root.resolve(strict=True)


def _acquire_lease(path: Path, *, nonblocking: bool) -> int | None:
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    try:
        operation = fcntl.LOCK_EX | (fcntl.LOCK_NB if nonblocking else 0)
        try:
            fcntl.flock(fd, operation)
        except BlockingIOError:
            os.close(fd)
            return None
        return fd
    except BaseException:
        os.close(fd)
        raise


@contextmanager
def managed_scratch(kind: str, *, root: Path | None = None) -> Iterator[Path]:
    """Create a marked, leased scratch directory and remove it on normal exit."""
    if kind not in _KINDS:
        raise ValueError("scratch kind is not managed by the harness")
    managed_root = _safe_root(root or default_scratch_root(), create=True)
    directory = Path(tempfile.mkdtemp(prefix=f"{kind}-", dir=managed_root))
    os.chmod(directory, 0o700)
    lease = _acquire_lease(directory / _LEASE, nonblocking=False)
    assert lease is not None
    marker = {
        "schema_version": 1,
        "managed_by": _MANAGED_BY,
        "scratch_id": directory.name,
        "kind": kind,
        "created_at": time.time(),
        "owner_uid": os.getuid(),
        "pid": os.getpid(),
    }
    marker_path = directory / _MARKER
    descriptor = os.open(marker_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY
                         | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(marker, stream, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        yield directory
    finally:
        fcntl.flock(lease, fcntl.LOCK_UN)
        os.close(lease)
        _remove_verified(managed_root, directory.name, expected_id=directory.name)


def _read_marker(directory: Path) -> dict[str, object] | None:
    marker_path = directory / _MARKER
    try:
        info = marker_path.lstat()
        if (not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode)
                or info.st_size > 4096):
            return None
        value = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    created_at = value.get("created_at") if isinstance(value, dict) else None
    owner_uid = value.get("owner_uid") if isinstance(value, dict) else None
    if (not isinstance(value, dict) or isinstance(value.get("schema_version"), bool)
            or value.get("schema_version") != 1
            or value.get("managed_by") != _MANAGED_BY
            or value.get("scratch_id") != directory.name
            or value.get("kind") not in _KINDS
            or isinstance(owner_uid, bool) or owner_uid != os.getuid()
            or isinstance(created_at, bool) or not isinstance(created_at, (int, float))
            or not math.isfinite(created_at) or created_at < 0):
        return None
    return value


def _contains_git_metadata(directory: Path) -> bool:
    for current, directories, files in os.walk(directory, followlinks=False):
        if ".git" in directories or ".git" in files:
            return True
        directories[:] = [name for name in directories
                          if not (Path(current) / name).is_symlink()]
    return False


def _remove_verified(root: Path, name: str, *, expected_id: str) -> bool:
    """Recheck ownership and atomically quarantine a single managed child."""
    if name in {"", ".", ".."} or Path(name).name != name:
        return False
    try:
        root = _safe_root(root, create=False)
        candidate = root / name
        before = candidate.lstat()
        if not stat.S_ISDIR(before.st_mode) or stat.S_ISLNK(before.st_mode):
            return False
        if candidate.resolve(strict=True).parent != root.resolve(strict=True):
            return False
        marker = _read_marker(candidate)
        if marker is None or marker.get("scratch_id") != expected_id:
            return False
        if _contains_git_metadata(candidate):
            return False
        lease_path = candidate / _LEASE
        lease_info = lease_path.lstat()
        if not stat.S_ISREG(lease_info.st_mode) or stat.S_ISLNK(lease_info.st_mode):
            return False
        lease_fd = _acquire_lease(lease_path, nonblocking=True)
        if lease_fd is None:
            return False
        try:
            current = candidate.lstat()
            if (current.st_dev, current.st_ino) != (before.st_dev, before.st_ino):
                return False
            quarantine = root / f".gc-{uuid.uuid4().hex}"
            os.rename(candidate, quarantine)
            quarantined = quarantine.lstat()
            if (quarantined.st_dev, quarantined.st_ino) != (before.st_dev, before.st_ino):
                os.rename(quarantine, candidate)
                return False
            shutil.rmtree(quarantine)
            return True
        finally:
            fcntl.flock(lease_fd, fcntl.LOCK_UN)
            os.close(lease_fd)
    except (OSError, ValueError):
        return False


def collect_stale(*, root: Path | None = None, min_age_s: float = 86_400,
                  now: float | None = None) -> dict[str, object]:
    """Remove only stale, owned, inactive scratch folders; report all skips."""
    if (isinstance(min_age_s, bool) or not isinstance(min_age_s, (int, float))
            or not math.isfinite(min_age_s) or min_age_s < 0):
        raise ValueError("min_age_s must be a finite non-negative number")
    current_time = time.time() if now is None else now
    if (isinstance(current_time, bool) or not isinstance(current_time, (int, float))
            or not math.isfinite(current_time)):
        raise ValueError("now must be a finite number")
    managed_root = _safe_root(root or default_scratch_root(), create=False)
    if not managed_root.exists():
        return {"removed": [], "active": [], "too_young": [], "unmanaged": []}
    cutoff = current_time - min_age_s
    removed: list[str] = []
    active: list[str] = []
    too_young: list[str] = []
    unmanaged: list[str] = []
    for entry in managed_root.iterdir():
        try:
            info = entry.lstat()
            if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
                unmanaged.append(entry.name)
                continue
            marker = _read_marker(entry)
            if marker is None:
                unmanaged.append(entry.name)
                continue
            if _contains_git_metadata(entry):
                unmanaged.append(entry.name)
                continue
            if float(marker["created_at"]) > cutoff:
                too_young.append(entry.name)
                continue
            if _remove_verified(managed_root, entry.name, expected_id=str(marker["scratch_id"])):
                removed.append(entry.name)
            else:
                active.append(entry.name)
        except OSError:
            unmanaged.append(entry.name)
    return {"removed": sorted(removed), "active": sorted(active),
            "too_young": sorted(too_young), "unmanaged": sorted(unmanaged)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="harness-scratch-gc")
    sub = parser.add_subparsers(dest="command", required=True)
    collect = sub.add_parser("collect", help="collect stale managed scratch only")
    collect.add_argument("--root", type=Path)
    collect.add_argument("--min-age-s", type=float, default=86_400)
    args = parser.parse_args(argv)
    result = collect_stale(root=args.root, min_age_s=args.min_age_s)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
