"""Statistical analysis service for metrics.

Implements:
- Descriptive statistics (mean, min, max, std, median)
- IQR-based anomaly detection
- Moving average calculation

Cache strategy
--------------
All read paths go through ``cache_service`` which owns key naming and
TTL constants (configured in ``settings.CACHE_TTL_*``).

Cache *invalidation* is handled by the write path in
``datapoint_service.create_datapoints`` — this service never deletes
cache entries.  The separation keeps read-side and write-side concerns
cleanly isolated.
"""
from __future__ import annotations

import statistics
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidDataError, MetricNotFoundError
from app.models.datapoint import Datapoint
from app.models.metric import Metric
from app.services import cache_service

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _fetch_all_values(db: AsyncSession, metric_name: str) -> list[float]:
    """Return all datapoint values for *metric_name* ordered by timestamp.

    Raises:
        MetricNotFoundError: When the metric does not exist.
        InvalidDataError: When the metric has no datapoints.
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


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


async def get_stats(
    db: AsyncSession,
    metric_name: str,
) -> dict:
    """Return descriptive statistics for *metric_name*.

    Results are cached via ``cache_service`` with ``CACHE_TTL_STATS``
    TTL (default 300 s).  The cache is invalidated automatically
    when new datapoints are written via ``datapoint_service``.

    Args:
        db: Active async SQLAlchemy session.
        metric_name: Name of the metric to analyse.

    Returns:
        Dict with keys: ``metric_name``, ``count``, ``mean``, ``min``,
        ``max``, ``std_dev`` (sample std, ``None`` if count < 2), ``median``.

    Raises:
        MetricNotFoundError: When the metric does not exist.
        InvalidDataError: When the metric has no datapoints.
    """
    cached = await cache_service.get_stats_cache(metric_name)
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
    await cache_service.set_stats_cache(metric_name, result)
    return result


async def get_anomalies(
    db: AsyncSession,
    metric_name: str,
) -> dict:
    """Return datapoints that are statistical outliers.

    Uses the **IQR (Interquartile Range)** method, which is more robust
    to extreme values than the classic 3-sigma rule::

        Q1, Q3 = 25th and 75th percentiles
        IQR = Q3 - Q1
        lower = Q1 - 1.5 * IQR
        upper = Q3 + 1.5 * IQR

    Values outside ``[lower, upper]`` are flagged as anomalies.

    Results are cached via ``cache_service`` with ``CACHE_TTL_ANOMALIES``
    TTL (default 60 s).

    Args:
        db: Active async SQLAlchemy session.
        metric_name: Name of the metric to analyse.

    Returns:
        Dict with keys: ``metric_name``, ``anomaly_count``,
        ``threshold_lower``, ``threshold_upper``, ``anomalies`` (list of
        ``{"id": ..., "value": ..., "timestamp": ...}``).

    Raises:
        MetricNotFoundError: When the metric does not exist.
        InvalidDataError: When the metric has no datapoints.
    """
    cached = await cache_service.get_anomalies_cache(metric_name)
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
    sorted_vals = sorted(values)

    # IQR method — more robust to extreme values than 3-sigma
    q1, _q2, q3 = statistics.quantiles(sorted_vals, n=4)
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr

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
        "threshold_lower": round(lower, 6),
        "threshold_upper": round(upper, 6),
        "anomaly_count": len(anomalies),
        "anomalies": anomalies,
    }
    await cache_service.set_anomalies_cache(metric_name, result)
    return result


async def get_moving_average(
    db: AsyncSession,
    metric_name: str,
    window: int = 7,
) -> dict:
    """Return a simple moving-average series for *metric_name*.

    The window is **point-based** (not time-based): each output value
    is the mean of the current point and the previous ``window - 1`` points.

    Results are cached via ``cache_service`` with ``CACHE_TTL_MA``
    TTL (default 600 s), keyed by both metric name and window size.

    Args:
        db: Active async SQLAlchemy session.
        metric_name: Name of the metric to analyse.
        window: Window size in number of data points (≥ 1).

    Returns:
        Dict with keys: ``metric_name``, ``window``, ``data_points``
        (list of ``{"timestamp": ..., "value": ..., "moving_average": ...}``).

    Raises:
        InvalidDataError: When ``window < 1`` or the metric has no datapoints.
        MetricNotFoundError: When the metric does not exist.
    """
    if window < 1:
        raise InvalidDataError("window 必须大于 0")

    cached = await cache_service.get_moving_average_cache(metric_name, window)
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
    await cache_service.set_moving_average_cache(metric_name, window, result)
    return result
