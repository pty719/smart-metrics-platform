"""Business logic for metric operations.

All database access happens here; the API layer only calls these functions
and translates the results into HTTP responses.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DuplicateMetricError, MetricNotFoundError
from app.models.metric import Metric


async def create_metric(
    db: AsyncSession,
    name: str,
    unit: Optional[str] = None,
    description: Optional[str] = None,
) -> Metric:
    """Create a new metric.

    Args:
        db: An active SQLAlchemy async session.
        name: Unique human-readable metric identifier.
        unit: Optional unit label, e.g. "人", "ms".
        description: Optional long-form description.

    Returns:
        The newly created ``Metric`` ORM instance (already persisted).

    Raises:
        DuplicateMetricError: If a metric with the same ``name`` already
            exists.
    """
    existing = await db.scalar(select(Metric).where(Metric.name == name))
    if existing is not None:
        raise DuplicateMetricError(name)

    metric = Metric(name=name, unit=unit, description=description)
    db.add(metric)
    await db.flush()  # populate metric.id
    await db.refresh(metric)
    return metric


async def get_metrics(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[Metric], int]:
    """Return a paginated list of metrics and the total count.

    Args:
        db: An active SQLAlchemy async session.
        skip: Number of records to skip (offset).
        limit: Maximum number of records to return.

    Returns:
        A ``(items, total)`` tuple.
    """
    total = await db.scalar(select(func.count(Metric.id)))
    stmt = (
        select(Metric)
        .order_by(Metric.id.asc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.scalars(stmt)
    return result.all(), total or 0


async def get_metric_by_name(
    db: AsyncSession,
    name: str,
) -> Metric:
    """Fetch a single metric by its unique name.

    Args:
        db: An active SQLAlchemy async session.
        name: The ``name`` value to look up.

    Returns:
        The matching ``Metric`` instance.

    Raises:
        MetricNotFoundError: If no metric with the given ``name`` exists.
    """
    metric = await db.scalar(select(Metric).where(Metric.name == name))
    if metric is None:
        raise MetricNotFoundError(name)
    return metric


async def delete_metric(
    db: AsyncSession,
    name: str,
) -> None:
    """Delete a metric and all its associated datapoints (CASCADE).

    Args:
        db: An active SQLAlchemy async session.
        name: The ``name`` of the metric to delete.

    Raises:
        MetricNotFoundError: If no metric with the given ``name`` exists.
    """
    metric = await get_metric_by_name(db, name)
    await db.delete(metric)
