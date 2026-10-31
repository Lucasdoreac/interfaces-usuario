"""Conservative version-delta analysis for stable numeric release versions."""

from __future__ import annotations

import re
from typing import Any


_STABLE_VERSION = re.compile(
    r"(?P<release>(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*))*)"
    r"(?:\.post(?P<post>0|[1-9][0-9]*))?(?:\+[A-Za-z0-9.-]+)?\Z"
)
_PRERELEASE_VERSION = re.compile(
    r"(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*))*(?:a|b|rc|\.dev)[0-9]+",
    re.IGNORECASE,
)
_ORDER = {"none": 0, "patch": 1, "minor": 2, "major": 3}


def _release_tuple(value: str) -> tuple[int, ...] | None:
    match = _STABLE_VERSION.fullmatch(value)
    if not match:
        return None
    return tuple(int(part) for part in match.group("release").split("."))


def is_stable_release(value: str) -> bool:
    """Accept numeric stable releases, post releases, and local build labels."""
    return bool(_STABLE_VERSION.fullmatch(value))


def classify_version_change(old: str, new: str) -> str | None:
    """Return none/patch/minor/major, or None when version semantics are unknown."""
    if old == new:
        return "none"
    before, after = _release_tuple(old), _release_tuple(new)
    if before is None or after is None:
        if _PRERELEASE_VERSION.search(old) or _PRERELEASE_VERSION.search(new):
            # A changed pre-release transitive receives the highest package
            # delta, so only high-risk evidence can proceed.
            return "major"
        return None
    width = max(3, len(before), len(after))
    before = before + (0,) * (width - len(before))
    after = after + (0,) * (width - len(after))
    if before == after:
        old_post = _STABLE_VERSION.fullmatch(old).group("post")
        new_post = _STABLE_VERSION.fullmatch(new).group("post")
        if old_post != new_post:
            return "patch"
        return "none"
    if before[0] != after[0]:
        return "major"
    if before[1] != after[1]:
        return "major" if before[0] == 0 else "minor"
    old_post = _STABLE_VERSION.fullmatch(old).group("post")
    new_post = _STABLE_VERSION.fullmatch(new).group("post")
    if old_post != new_post:
        return "patch"
    return "patch"


def package_delta(changes: list[dict[str, Any]]) -> tuple[str | None, list[str]]:
    """Aggregate all package changes; additions/removals are structural changes."""
    if not changes:
        return "none", []
    levels: list[str] = []
    reasons: list[str] = []
    for change in changes:
        if not isinstance(change, dict):
            return None, ["package change record has an unsupported format"]
        old, new = change.get("from"), change.get("to")
        if old is None or new is None:
            levels.append("major")
            continue
        old_versions = [old] if isinstance(old, str) else old
        new_versions = [new] if isinstance(new, str) else new
        if (not isinstance(old_versions, list) or not isinstance(new_versions, list)
                or not old_versions or not new_versions
                or any(not isinstance(item, str) for item in [*old_versions, *new_versions])):
            return None, ["package version change does not contain complete version sets"]
        for old_version in old_versions:
            for new_version in new_versions:
                level = classify_version_change(old_version, new_version)
                if level is None:
                    reasons.append(f"unsupported version scheme for {change.get('name', 'package')}")
                else:
                    levels.append(level)
    if reasons or not levels:
        return None, sorted(set(reasons or ["package delta could not be calculated"]))
    return max(levels, key=_ORDER.__getitem__), []
