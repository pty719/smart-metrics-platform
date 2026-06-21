"""Math utility functions (pure, no side-effects).

All functions here operate on plain Python lists/numbers and have zero
dependencies on external state (DB, Redis, etc.).
"""
from __future__ import annotations

from typing import List


def compute_percentile(values: List[float], percentile: float) -> float:
    """Compute the p-th percentile of *values* using linear interpolation.

    Args:
        values: Non-empty list of numeric values.
        percentile: Desired percentile in the range [0, 100].

    Returns:
        The interpolated p-th percentile value.

    Raises:
        ValueError: If *values* is empty or *percentile* is out of range.

    Examples:
        >>> compute_percentile([1, 2, 3, 4, 5], 50)
        3.0
        >>> compute_percentile([1, 2, 3, 4, 5], 90)
        4.6
    """
    if not values:
        raise ValueError("values list must not be empty")
    if not (0 <= percentile <= 100):
        raise ValueError(f"percentile must be in [0, 100], got {percentile}")

    sorted_vals = sorted(values)
    n = len(sorted_vals)
    rank = percentile / 100 * (n - 1)
    lower = int(rank)
    upper = lower + 1
    frac = rank - lower

    if upper >= n:
        return float(sorted_vals[-1])
    return float(sorted_vals[lower] + frac * (sorted_vals[upper] - sorted_vals[lower]))


def sliding_window_averages(values: List[float], window: int) -> List[float]:
    """Compute a simple moving average with the given window size.

    Positions with fewer than *window* preceding values return the average
    of available values (expanding window at the start).

    Args:
        values: Time-ordered list of numeric values.
        window: Rolling window size (must be >= 1).

    Returns:
        List of the same length as *values* with moving-average values.

    Raises:
        ValueError: If *window* is less than 1.

    Examples:
        >>> sliding_window_averages([1, 2, 3, 4, 5], 3)
        [1.0, 1.5, 2.0, 3.0, 4.0]
    """
    if window < 1:
        raise ValueError(f"window must be >= 1, got {window}")
    result: List[float] = []
    for i, _ in enumerate(values):
        start = max(0, i - window + 1)
        window_values = values[start : i + 1]
        result.append(sum(window_values) / len(window_values))
    return result
