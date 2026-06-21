"""Business logic for datapoint operations.

Handles uploading, querying, and retrieving latest values for datapoints
belonging to a metric.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidDataError, MetricNotFoundError
from app.models.datapoint import Datapoint
from app.models.metric import Metric


async def _get_metric_or_404(db: AsyncSession, name: str) -> Metric:
    """Return a ``Metric`` by name or raise ``MetricNotFoundError``."""
    metric = await db.scalar(select(Metric).where(Metric.name == name))
    if metric is None:
        raise MetricNotFoundError(name)
    return metric


async def create_datapoints(
    db: AsyncSession,
    metric_name: str,
    datapoints: list[dict],
) -> list[Datapoint]:
    """Bulk-insert datapoints for a metric.

    Args:
        db: An active SQLAlchemy async session.
        metric_name: The ``name`` of the parent metric.
        datapoints: A list of ``{"value": float, "timestamp"?: datetime}``
            dicts.  When ``timestamp`` is ``None`` the server time
            (UTC) is used.

    Returns:
        The list of newly created ``Datapoint`` ORM instances.

    Raises:
        MetricNotFoundError: If no metric with ``metric_name`` exists.
        InvalidDataError: If any ``value`` is not finite.
    """
    metric = await _get_metric_or_404(db, metric_name)
    now = datetime.now(timezone.utc)

    records: list[Datapoint] = []
    for item in datapoints:
        value = item["value"]
        import math

        if math.isnan(value) or math.isinf(value):
            raise InvalidDataError(f"value must be finite, got {value}")

        ts = item.get("timestamp") or now
        records.append(
            Datapoint(metric_id=metric.id, timestamp=ts, value=value)
        )

    db.add_all(records)
    await db.flush()
    for r in records:
        await db.refresh(r)
    return records


async def get_datapoints(
    db: AsyncSession,
    metric_name: str,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 1000,
) -> tuple[list[Datapoint], int]:
    """Return paginated datapoints for a metric, optionally filtered by time range.

    Args:
        db: An active SQLAlchemy async session.
        metric_name: The ``name`` of the parent metric.
        start: Inclusive lower bound (UTC).  ``None`` means no lower bound.
        end: Inclusive upper bound (UTC).  ``None`` means no upper bound.
        skip: Number of records to skip (offset).
        limit: Maximum number of records to return.

    Returns:
        A ``(items, total)`` tuple.

    Raises:
        MetricNotFoundError: If no metric with ``metric_name`` exists.
    """
    metric = await _get_metric_or_404(db, metric_name)

    where = [Datapoint.metric_id == metric.id]
    if start is not None:
        where.append(Datapoint.timestamp >= start)
    if end is not None:
        where.append(Datapoint.timestamp <= end)

    total = await db.scalar(select(func.count(Datapoint.id)).where(*where)) or 0
    stmt = (
        select(Datapoint)
        .where(*where)
        .order_by(Datapoint.timestamp.asc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.scalars(stmt)
    return result.all(), total


async def get_latest_value(
    db: AsyncSession,
    metric_name: str,
) -> Datapoint:
    """Return the most recent datapoint for a metric.

    Args:
        db: An active SQLAlchemy async session.
        metric_name: The ``name`` of the parent metric.

    Returns:
        The latest ``Datapoint`` instance (by ``timestamp``).

    Raises:
        MetricNotFoundError: If no metric with ``metric_name`` exists.
        InvalidDataError: If the metric has no datapoints yet.
    """
    metric = await _get_metric_or_404(db, metric_name)

    latest = await db.scalar(
        select(Datapoint)
        .where(Datapoint.metric_id == metric.id)
        .order_by(Datapoint.timestamp.desc())
        .limit(1)
    )
    if latest is None:
        raise InvalidDataError(
            f"metric '{metric_name}' has no data points yet"
        )
    return latest
