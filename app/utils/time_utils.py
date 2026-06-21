"""Time-related utility functions (pure, no side-effects)."""
from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Return the current UTC datetime (timezone-aware).

    Returns:
        Current UTC datetime with ``timezone.utc`` tzinfo.
    """
    return datetime.now(tz=timezone.utc)


def ensure_utc(dt: datetime) -> datetime:
    """Ensure a datetime is UTC-aware.

    If *dt* is naive (no tzinfo), it is treated as UTC and made aware.

    Args:
        dt: The datetime to normalise.

    Returns:
        A timezone-aware UTC datetime.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
