"""Deterministic quota capacity and executor selection shared by adapters."""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Mapping, Sequence


@dataclass(frozen=True)
class Window:
    remaining: float
    duration_s: float
    resets_at: datetime


@dataclass(frozen=True)
class Snapshot:
    observed_at: datetime
    windows: Sequence[Window]
    status: str = "allowed"
    limit_reached: bool = False


@dataclass(frozen=True)
class Decision:
    executor: str | None
    reason: str
    capacities: Mapping[str, float]
    weights: Mapping[str, float]


def _finite_number(value: object) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(float(value))
    except (OverflowError, ValueError):
        return False


def capacity(snapshot: Snapshot | None, now: datetime, *, max_age_s: float = 300.0) -> float | None:
    """Return min(window remaining * duration / time-to-reset), or None if untrusted."""
    if (not isinstance(snapshot, Snapshot) or not isinstance(now, datetime)
            or now.utcoffset() is None or not isinstance(snapshot.status, str)
            or not isinstance(snapshot.limit_reached, bool)
            or not isinstance(snapshot.windows, (list, tuple))):
        return None
    if not isinstance(snapshot.observed_at, datetime) or snapshot.observed_at.utcoffset() is None:
        return None
    if not _finite_number(max_age_s) or max_age_s < 0:
        return None
    # A rejection/limit marker, or a zero-remaining window with a future
    # reset, is monotonic proof of unavailability beyond ordinary snapshot age.
    # When its reset passes the proof expires and a reread is required.
    if snapshot.status not in {"allowed", "rejected"}:
        return None
    if not isinstance(snapshot.windows, (list, tuple)):
        return None
    future_resets = []
    zero_window = False
    for window in snapshot.windows:
        if (not isinstance(window, Window) or not isinstance(window.resets_at, datetime)
                or window.resets_at.utcoffset() is None):
            continue
        if window.resets_at > now:
            future_resets.append(window.resets_at)
            zero_window = zero_window or (
                _finite_number(window.remaining) and window.remaining == 0
                and _finite_number(window.duration_s) and window.duration_s > 0
            )
    if future_resets and (snapshot.status == "rejected" or snapshot.limit_reached or zero_window):
        return 0.0
    age = (now - snapshot.observed_at).total_seconds()
    if age < 0 or age > max_age_s:
        return None
    if snapshot.status != "allowed" or not snapshot.windows:
        return None
    values: list[float] = []
    for window in snapshot.windows:
        if (not isinstance(window, Window)
                or not _finite_number(window.remaining) or not 0 <= window.remaining <= 1
                or not _finite_number(window.duration_s) or window.duration_s <= 0
                or not isinstance(window.resets_at, datetime) or window.resets_at.utcoffset() is None):
            return None
        until_reset = (window.resets_at - now).total_seconds()
        if until_reset <= 0 or not math.isfinite(until_reset):
            return None
        value = window.remaining * window.duration_s / until_reset
        if not math.isfinite(value) or value < 0:
            return None
        values.append(value)
    return min(values)


def select(
    snapshots: Mapping[str, Snapshot | None], *, primary: str, selection_key: str,
    now: datetime, max_age_s: float = 300.0,
) -> Decision:
    """Select among valid capacities using a stable hash and normalized weights.

    Missing/unknown snapshots permit only a primary attempt. They never authorize
    an alternative. Zero capacity (including a proved rejection) is unavailable.
    """
    if not isinstance(primary, str) or not isinstance(selection_key, str):
        raise ValueError("primary and selection_key must be strings")
    if not isinstance(snapshots, Mapping) or any(not isinstance(name, str) for name in snapshots):
        raise ValueError("snapshots must map executor names to normalized snapshots")
    capacities = {name: value for name, snap in snapshots.items()
                  if (value := capacity(snap, now, max_age_s=max_age_s)) is not None and value > 0}
    scale = max(capacities.values(), default=0.0)
    scaled = {name: value / scale for name, value in capacities.items()} if scale else {}
    total = math.fsum(scaled.values())
    weights = ({name: value / total for name, value in scaled.items()} if total > 0 else {})
    if weights:
        last = sorted(weights)[-1]
        weights[last] = 1.0 - math.fsum(value for name, value in weights.items() if name != last)
    if not weights:
        if primary in snapshots and capacity(snapshots[primary], now, max_age_s=max_age_s) is None:
            return Decision(primary, "primary_unknown_attempt", {}, {})
        return Decision(None, "all_unavailable", {}, {})
    digest = hashlib.sha256(selection_key.encode("utf-8")).digest()
    point = int.from_bytes(digest[:8], "big") / 2**64
    cumulative = 0.0
    chosen = next(iter(weights))
    for name in sorted(weights):
        cumulative += weights[name]
        if point < cumulative:
            chosen = name
            break
    return Decision(chosen, "proportional_capacity", capacities, weights)
