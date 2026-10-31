"""Digest helpers for immutable vendored harness snapshots.

PARADIGMA: determinístico
Hashes only source files; generated setuptools/uv build outputs are ignored.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def snapshot_digest(vendor: Path) -> str:
    """Return a stable digest of a vendored distribution source tree."""
    vendor = vendor.resolve()
    pyproject = vendor / "pyproject.toml"
    package = vendor / "update_vanguard"
    if not pyproject.is_file() or not package.is_dir():
        raise ValueError("vendored distribution requires pyproject.toml and update_vanguard/")

    files: dict[str, bytes] = {"pyproject.toml": pyproject.read_bytes()}
    for path in sorted(vendor.rglob("*")):
        if path.is_symlink():
            raise ValueError("vendored distribution cannot contain symlinks")
        if not path.is_file():
            continue
        relative = path.relative_to(vendor)
        if ("build" in relative.parts or "__pycache__" in relative.parts
                or path.suffix == ".pyc"
                or any(part.endswith(".egg-info") for part in relative.parts)):
            continue
        key = relative.as_posix()
        if key != "pyproject.toml":
            files[key] = path.read_bytes()

    digest = hashlib.sha256()
    for name, content in sorted(files.items()):
        encoded_name = name.encode("utf-8")
        digest.update(len(encoded_name).to_bytes(4, "big"))
        digest.update(encoded_name)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def verify_snapshot(vendor: Path, expected_digest: str) -> str:
    """Return the digest or raise when the source tree differs from its pin."""
    if (len(expected_digest) != 64
            or any(char not in "0123456789abcdef" for char in expected_digest)):
        raise ValueError("snapshot digest must be a lowercase SHA-256")
    actual = snapshot_digest(vendor)
    if actual != expected_digest:
        raise ValueError("vendored source does not match its pinned digest")
    return actual
