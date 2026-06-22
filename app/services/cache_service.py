"""Cache service — centralises all Redis key naming and invalidation logic.

Design rules (AGENTS.md §3.2):
- This module owns every cache key pattern; no other module may
  construct raw Redis keys directly.
- Cache invalidation is triggered by the *data mutation* path
  (``datapoint_service.create_datapoints``), not by the read path.
- All public functions are ``async``.

Key schema::

    stats:{metric_name}:stats          TTL = CACHE_TTL_STATS   (300 s)
    stats:{metric_name}:anomalies      TTL = CACHE_TTL_ANOMALIES (60 s)
    stats:{metric_name}:ma_{window}    TTL = CACHE_TTL_MA      (600 s)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from redis.asyncio import Redis

from app.config import settings
from app.core.redis_client import get_redis

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Key helpers (single source of truth)
# ---------------------------------------------------------------------------

_PREFIX = "stats"


def stats_key(metric_name: str) -> str:
    """Return the Redis key for descriptive statistics of *metric_name*."""
    return f"{_PREFIX}:{metric_name}:stats"


def anomalies_key(metric_name: str) -> str:
    """Return the Redis key for anomaly detection of *metric_name*."""
    return f"{_PREFIX}:{metric_name}:anomalies"


def moving_average_key(metric_name: str, window: int) -> str:
    """Return the Redis key for moving average of *metric_name* with *window*."""
    return f"{_PREFIX}:{metric_name}:ma_{window}"


def _all_metric_keys_pattern(metric_name: str) -> str:
    """Glob pattern that matches **all** cache keys for *metric_name*."""
    return f"{_PREFIX}:{metric_name}:*"


# ---------------------------------------------------------------------------
# Low-level get / set
# ---------------------------------------------------------------------------


def _json_serializer(obj: Any) -> Any:
    """Handle non-standard JSON types when serialising cache values."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serialisable")


async def get_cached(key: str, redis: Redis | None = None) -> Any | None:
    """Fetch and deserialise a cached value.

    Args:
        key: Redis key to look up.
        redis: Optional Redis client; uses the global singleton when omitted.

    Returns:
        Deserialised Python object, or ``None`` on cache miss.
    """
    r = redis or get_redis()
    raw = await r.get(key)
    if raw is not None:
        return json.loads(raw)
    return None


async def set_cached(
    key: str,
    value: Any,
    ttl: int,
    redis: Redis | None = None,
) -> None:
    """Serialise and store *value* with a TTL.

    Args:
        key: Redis key to write.
        value: JSON-serialisable Python object.
        ttl: Time-to-live in seconds.
        redis: Optional Redis client; uses the global singleton when omitted.
    """
    r = redis or get_redis()
    await r.set(key, json.dumps(value, default=_json_serializer), ex=ttl)


# ---------------------------------------------------------------------------
# Per-type convenience wrappers (keeps TTL config in one place)
# ---------------------------------------------------------------------------


async def get_stats_cache(
    metric_name: str,
    redis: Redis | None = None,
) -> Any | None:
    """Return the cached statistics dict for *metric_name*, or ``None``."""
    return await get_cached(stats_key(metric_name), redis)


async def set_stats_cache(
    metric_name: str,
    value: Any,
    redis: Redis | None = None,
) -> None:
    """Cache statistics for *metric_name* with ``CACHE_TTL_STATS`` TTL."""
    await set_cached(stats_key(metric_name), value, settings.CACHE_TTL_STATS, redis)


async def get_anomalies_cache(
    metric_name: str,
    redis: Redis | None = None,
) -> Any | None:
    """Return the cached anomalies dict for *metric_name*, or ``None``."""
    return await get_cached(anomalies_key(metric_name), redis)


async def set_anomalies_cache(
    metric_name: str,
    value: Any,
    redis: Redis | None = None,
) -> None:
    """Cache anomaly results for *metric_name* with ``CACHE_TTL_ANOMALIES`` TTL."""
    await set_cached(
        anomalies_key(metric_name), value, settings.CACHE_TTL_ANOMALIES, redis
    )


async def get_moving_average_cache(
    metric_name: str,
    window: int,
    redis: Redis | None = None,
) -> Any | None:
    """Return the cached moving-average dict for *metric_name*/*window*, or ``None``."""
    return await get_cached(moving_average_key(metric_name, window), redis)


async def set_moving_average_cache(
    metric_name: str,
    window: int,
    value: Any,
    redis: Redis | None = None,
) -> None:
    """Cache moving-average results with ``CACHE_TTL_MA`` TTL."""
    await set_cached(
        moving_average_key(metric_name, window),
        value,
        settings.CACHE_TTL_MA,
        redis,
    )


# ---------------------------------------------------------------------------
# Invalidation
# ---------------------------------------------------------------------------


async def invalidate_metric_cache(
    metric_name: str,
    redis: Redis | None = None,
) -> int:
    """Delete **all** cached results for *metric_name*.

    Uses ``SCAN`` + ``UNLINK`` (non-blocking delete) to avoid blocking
    the Redis server when many moving-average windows are cached.

    This should be called whenever new datapoints are written for a metric
    so that stale statistics, anomaly results, and moving averages are
    evicted immediately.

    Args:
        metric_name: The metric whose cached data should be purged.
        redis: Optional Redis client; uses the global singleton when omitted.

    Returns:
        Number of keys deleted.
    """
    r = redis or get_redis()
    pattern = _all_metric_keys_pattern(metric_name)

    deleted = 0
    cursor = 0
    while True:
        cursor, keys = await r.scan(cursor=cursor, match=pattern, count=100)
        if keys:
            await r.unlink(*keys)
            deleted += len(keys)
            logger.debug(
                "cache invalidated",
                extra={"metric_name": metric_name, "keys_deleted": len(keys)},
            )
        if cursor == 0:
            break

    if deleted:
        logger.info(
            "metric cache invalidated",
            extra={"metric_name": metric_name, "total_keys_deleted": deleted},
        )
    return deleted


async def invalidate_stats_only(
    metric_name: str,
    redis: Redis | None = None,
) -> None:
    """Delete only the statistics cache entry for *metric_name*.

    Useful when you know that only aggregated stats have changed (e.g. after
    a soft-delete of a single datapoint), without needing to flush anomaly
    and moving-average caches.

    Args:
        metric_name: The metric to invalidate.
        redis: Optional Redis client; uses the global singleton when omitted.
    """
    r = redis or get_redis()
    await r.unlink(stats_key(metric_name))
