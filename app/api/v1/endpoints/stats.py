"""API endpoints for statistical analysis.

Implements:
- GET  /api/v1/metrics/{name}/stats         — descriptive statistics
- GET  /api/v1/metrics/{name}/anomalies    — 3-sigma anomaly detection
- GET  /api/v1/metrics/{name}/moving-average — simple moving average
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, verify_api_key
from app.api.responses import success_response
from app.api.v1.schemas.stats import (
    AnomaliesResponse,
    MovingAverageResponse,
    StatsResponse,
)
from app.services import stats_service

router = APIRouter(prefix="/metrics", dependencies=[Depends(verify_api_key)])


@router.get("/{name}/stats", response_model=dict)
async def get_stats(
    name: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Return descriptive statistics for a metric.

    Returns ``mean``, ``min``, ``max``, ``std_dev``, ``median``,
    and the total ``count`` of data points.

    Results are cached in Redis (TTL configured in ``CACHE_TTL_STATS``).

    Args:
        name: Metric name.
        db: Injected database session.

    Returns:
        Standardised success response with stats in ``data``.

    Raises:
        MetricNotFoundError (→ 404): When the metric does not exist.
        InvalidDataError (→ 422): When the metric has no data points.
    """
    result = await stats_service.get_stats(db, metric_name=name)
    return success_response(result)


@router.get("/{name}/anomalies", response_model=dict)
async def get_anomalies(
    name: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Detect anomalies using the IQR (Interquartile Range) method.

    Values outside ``[Q1 - 1.5*IQR, Q3 + 1.5*IQR]`` are flagged
    as anomalies.  This is more robust to extreme values than the classic
    3-sigma rule.

    Results are cached in Redis (TTL configured in
    ``CACHE_TTL_ANOMALIES``).

    Args:
        name: Metric name.
        db: Injected database session.

    Returns:
        Standardised success response with ``anomalies`` list in ``data``.

    Raises:
        MetricNotFoundError (→ 404): When the metric does not exist.
        InvalidDataError (→ 422): When the metric has no data points.
    """
    result = await stats_service.get_anomalies(db, metric_name=name)
    return success_response(result)


@router.get("/{name}/moving-average", response_model=dict)
async def get_moving_average(
    name: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    window: int = Query(7, ge=1, description="Moving window size (number of points)"),
) -> dict:
    """Return a simple moving-average series for a metric.

    The window is **point-based** (not time-based): each output point is
    the mean of the current point and the previous *window-1* points.

    Results are cached in Redis (TTL configured in ``CACHE_TTL_MA``).

    Args:
        name: Metric name.
        db: Injected database session.
        window: Number of adjacent points to average (≥ 1).

    Returns:
        Standardised success response with ``data_points`` in ``data``.

    Raises:
        MetricNotFoundError (→ 404): When the metric does not exist.
        InvalidDataError (→ 422): When ``window < 1`` or the metric
            has no data points.
    """
    result = await stats_service.get_moving_average(
        db, metric_name=name, window=window
    )
    return success_response(result)
