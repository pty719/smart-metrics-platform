"""Custom input validators (pure functions, no side-effects)."""
from __future__ import annotations

import re

_METRIC_NAME_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{0,99}$")


def validate_metric_name(name: str) -> str:
    """Validate that *name* is a legal metric identifier.

    Rules:
    - Starts with a letter (a-z, A-Z).
    - Contains only letters, digits, and underscores.
    - 1–100 characters long.

    Args:
        name: The metric name to validate.

    Returns:
        The validated name (unchanged).

    Raises:
        ValueError: If *name* does not match the required pattern.

    Examples:
        >>> validate_metric_name("daily_users")
        'daily_users'
        >>> validate_metric_name("123bad")
        Traceback (most recent call last):
            ...
        ValueError: Invalid metric name '123bad'. Must start with a letter ...
    """
    if not _METRIC_NAME_PATTERN.match(name):
        raise ValueError(
            f"Invalid metric name '{name}'. "
            "Must start with a letter, contain only letters/digits/underscores, "
            "and be 1–100 characters long."
        )
    return name
