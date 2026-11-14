"""Curve evaluation and target selection."""

from __future__ import annotations

from collections.abc import Sequence

Point = tuple[float, int]
Curve = Sequence[Point]


def desired_level(temp_c: float, curve: Curve) -> int:
    """Return the curve level for a temperature.

    Points are ordered from highest to lowest threshold. The last point is
    used below its threshold.
    """
    for threshold, level in curve:
        if temp_c >= threshold:
            return level
    return curve[-1][1]


def level_threshold(level: int, curve: Curve) -> float | None:
    """Return the threshold that selects a level, or None if it is skipped."""
    for threshold, point_level in curve:
        if point_level == level:
            return threshold
    return None


def compute_target(
    *,
    current: int | None,
    want: int,
    curve: Curve,
    control_temp: float,
    min_level: int,
    max_level: int,
    pin_active: bool,
    emergency: bool,
    hysteresis_c: float,
) -> int:
    """Return the next fan level.

    The fan moves one level at a time, except for an emergency, which jumps
    straight to the maximum. Hysteresis keeps a level until the temperature
    has fallen far enough below the threshold for the next level.
    """
    if emergency:
        return max_level
    if pin_active:
        return want
    if current is None:
        return want
    if want > current:
        return min(want, current + 1)
    if want < current:
        threshold = level_threshold(current, curve)
        if threshold is not None and control_temp > threshold - hysteresis_c:
            return current
        return max(min_level, max(want, current - 1))
    return current


def median_window(values: Sequence[float], window: int) -> float:
    """Return the median of the most recent values, capped to the window."""
    recent = list(values)[-max(1, window) :]
    if not recent:
        return 0.0
    ordered = sorted(recent)
    return ordered[len(ordered) // 2]
