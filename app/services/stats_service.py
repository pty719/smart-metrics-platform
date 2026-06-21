"""Statistical analysis service for metrics.

Implements:
- Descriptive statistics (mean, min, max, std, median)
- 3-sigma anomaly detection
- Moving average calculation

All expensive computations are cached in Redis with TTL configured
in ``settings.CACHE_TTL_*``.
"""
from __future__ import annotations

import json
import statistics
from datetime import datetime
from typing import Optional

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidDataError, MetricNotFoundError
from app.core.redis_client import get_redis
from app.models.datapoint import Datapoint
from app.models.metric import Metric

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _fetch_all_values(db: AsyncSession, metric_name: str) -> list[float]:
    """Return all datapoint values for *metric_name* ordered by timestamp.

    Raises ``MetricNotFoundError`` when the metric does not exist.
    Raises ``InvalidDataError`` when the metric has no datapoints.
    """
    metric = await db.scalar(select(Metric).where(Metric.name == metric_name))
    if metric is None:
        raise MetricNotFoundError(metric_name)

    rows = await db.scalars(
        select(Datapoint.value)
        .where(Datapoint.metric_id == metric.id)
        .order_by(Datapoint.timestamp.asc())
    )
    values = [float(v) for v in rows.all()]
    if not values:
        raise InvalidDataError(f"指标 '{metric_name}' 尚无数据点")
    return values


def _cache_key(metric_name: str, suffix: str) -> str:
    return f"stats:{metric_name}:{suffix}"


async def _get_cached(redis: Redis, key: str):
    raw = await redis.get(key)
    if raw is not None:
        return json.loads(raw)
    return None


async def _set_cached(redis: Redis, key: str, value, ttl: int) -> None:
    await redis.set(key, json.dumps(value, default=_json_serializer), ex=ttl)


def _json_serializer(obj):
    """Handle non-standard JSON types (e.g. datetime)."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


async def get_stats(
    db: AsyncSession,
    metric_name: str,
) -> dict:
    """Return descriptive statistics for *metric_name*.

    Cached in Redis for ``settings.CACHE_TTL_STATS`` seconds (default 300).

    Returns
    -------
    dict with keys: ``count``, ``mean``, ``min``, ``max``,
    ``std_dev`` (sample std, ``None`` if count < 2), ``median``.
    """
    from app.config import settings

    redis = get_redis()
    cache_key = _cache_key(metric_name, "stats")
    cached = await _get_cached(redis, cache_key)
    if cached is not None:
        return cached

    values = await _fetch_all_values(db, metric_name)
    n = len(values)
    mean = statistics.mean(values)
    median = statistics.median(values)
    std_dev = statistics.stdev(values) if n >= 2 else None

    result = {
        "metric_name": metric_name,
        "count": n,
        "mean": round(mean, 6),
        "min": round(min(values), 6),
        "max": round(max(values), 6),
        "std_dev": round(std_dev, 6) if std_dev is not None else None,
        "median": round(median, 6),
    }
    await _set_cached(redis, cache_key, result, settings.CACHE_TTL_STATS)
    return result


async def get_anomalies(
    db: AsyncSession,
    metric_name: str,
) -> dict:
    """Return datapoints that deviate more than 3σ from the mean.

    Uses the 3-sigma rule: values outside ``[mean - 3*σ, mean + 3*σ]``
    are considered anomalies.

    Cached in Redis for ``settings.CACHE_TTL_ANOMALIES`` seconds (default 60).

    Returns
    -------
    dict with keys: ``metric_name``, ``mean``, ``std_dev``,
    ``threshold_lower``, ``threshold_upper``, ``anomalies`` (list of
    ``{"id": ..., "value": ..., "timestamp": ...}``).
    """
    from app.config import settings

    redis = get_redis()
    cache_key = _cache_key(metric_name, "anomalies")
    cached = await _get_cached(redis, cache_key)
    if cached is not None:
        return cached

    metric = await db.scalar(select(Metric).where(Metric.name == metric_name))
    if metric is None:
        raise MetricNotFoundError(metric_name)

    rows = await db.scalars(
        select(Datapoint)
        .where(Datapoint.metric_id == metric.id)
        .order_by(Datapoint.timestamp.asc())
    )
    datapoints = rows.all()
    if not datapoints:
        raise InvalidDataError(f"指标 '{metric_name}' 尚无数据点")

    values = [float(dp.value) for dp in datapoints]
    mean = statistics.mean(values)
    std_dev = statistics.stdev(values) if len(values) >= 2 else 0.0

    lower = mean - 3 * std_dev
    upper = mean + 3 * std_dev

    anomalies = []
    for dp in datapoints:
        v = float(dp.value)
        if v < lower or v > upper:
            anomalies.append({
                "id": dp.id,
                "value": float(dp.value),
                "timestamp": dp.timestamp,
            })

    result = {
        "metric_name": metric_name,
        "mean": round(mean, 6),
        "std_dev": round(std_dev, 6) if len(values) >= 2 else None,
        "threshold_lower": round(lower, 6),
        "threshold_upper": round(upper, 6),
        "anomaly_count": len(anomalies),
        "anomalies": anomalies,
    }
    await _set_cached(redis, cache_key, result, settings.CACHE_TTL_ANOMALIES)
    return result


async def get_moving_average(
    db: AsyncSession,
    metric_name: str,
    window: int = 7,
) -> dict:
    """Return a simple moving-average series for *metric_name*.

    Parameters
    ----------
    window : int, default ``7``
        Window size in number of data points (not time-based).

    Cached in Redis for ``settings.CACHE_TTL_MA`` seconds (default 600).

    Returns
    -------
    dict with keys: ``metric_name``, ``window``, ``data_points`` (list of
    ``{"timestamp": ..., "value": ..., "moving_average": ...}``).
    """
    from app.config import settings

    if window < 1:
        raise InvalidDataError("window 必须大于 0")

    redis = get_redis()
    cache_key = _cache_key(metric_name, f"ma_{window}")
    cached = await _get_cached(redis, cache_key)
    if cached is not None:
        return cached

    metric = await db.scalar(select(Metric).where(Metric.name == metric_name))
    if metric is None:
        raise MetricNotFoundError(metric_name)

    rows = await db.scalars(
        select(Datapoint)
        .where(Datapoint.metric_id == metric.id)
        .order_by(Datapoint.timestamp.asc())
    )
    datapoints = rows.all()
    if not datapoints:
        raise InvalidDataError(f"指标 '{metric_name}' 尚无数据点")

    result_series: list[dict] = []
    for i, dp in enumerate(datapoints):
        start = max(0, i - window + 1)
        window_values = [float(datapoints[j].value) for j in range(start, i + 1)]
        ma = statistics.mean(window_values)
        result_series.append({
            "timestamp": dp.timestamp,
            "value": float(dp.value),
            "moving_average": round(ma, 6),
        })

    result = {
        "metric_name": metric_name,
        "window": window,
        "data_points": result_series,
    }
    await _set_cached(redis, cache_key, result, settings.CACHE_TTL_MA)
    return result
