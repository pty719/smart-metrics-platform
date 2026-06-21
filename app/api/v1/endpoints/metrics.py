"""API endpoints for metric management.

Implements:
- POST /api/v1/metrics              (create)
- GET  /api/v1/metrics              (list, paginated)
- GET  /api/v1/metrics/{name}      (get single)
- DELETE /api/v1/metrics/{name}     (delete)
- GET  /api/v1/metrics/{name}/latest  (latest value)
- POST /api/v1/metrics/{name}/data   (upload datapoints)
- GET  /api/v1/metrics/{name}/data   (query raw datapoints)
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, verify_api_key
from app.api.responses import success_response
from app.api.v1.schemas.metric import (
    DatapointBatchCreate,
    DatapointListResponse,
    DatapointResponse,
    LatestValueResponse,
    MetricCreate,
    MetricListResponse,
    MetricResponse,
)
from app.core.exceptions import AppException
from app.services import datapoint_service, metric_service

router = APIRouter(prefix="/metrics", dependencies=[Depends(verify_api_key)])


@router.post("", response_model=dict, status_code=201)
async def create_metric(
    body: MetricCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Create a new metric.

    Args:
        body: ``MetricCreate`` payload.
        db: Injected database session.

    Returns:
        Standardised success response with the created metric in ``data``.

    Raises:
        DuplicateMetricError (→ 409): When ``body.name`` already exists.
    """
    metric = await metric_service.create_metric(
        db, name=body.name, unit=body.unit, description=body.description
    )
    return success_response(
        MetricResponse.model_validate(metric).model_dump()
    )


@router.get("", response_model=dict)
async def list_metrics(
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Max records to return"),
) -> dict:
    """Return a paginated list of all metrics.

    Args:
        db: Injected database session.
        skip: Offset for pagination.
        limit: Page size (capped at 1000).

    Returns:
        Standardised success response with ``items`` and ``total`` in ``data``.
    """
    items, total = await metric_service.get_metrics(db, skip=skip, limit=limit)
    return success_response(
        MetricListResponse(
            items=[MetricResponse.model_validate(m) for m in items],
            total=total,
        ).model_dump()
    )


@router.get("/{name}", response_model=dict)
async def get_metric(
    name: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Return a single metric by its unique name.

    Args:
        name: The metric name to look up.
        db: Injected database session.

    Returns:
        Standardised success response with the metric in ``data``.

    Raises:
        MetricNotFoundError (→ 404): When no metric matches ``name``.
    """
    metric = await metric_service.get_metric_by_name(db, name=name)
    return success_response(
        MetricResponse.model_validate(metric).model_dump()
    )


@router.delete("/{name}", status_code=204)
async def delete_metric(
    name: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete a metric and all its datapoints (CASCADE).

    Args:
        name: The metric name to delete.
        db: Injected database session.

    Returns:
        ``None`` with HTTP 204.

    Raises:
        MetricNotFoundError (→ 404): When no metric matches ``name``.
    """
    await metric_service.delete_metric(db, name=name)
    return None  # FastAPI will return 204 No Content


@router.get("/{name}/latest", response_model=dict)
async def get_latest_value(
    name: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Return the most recent datapoint for a metric.

    Args:
        name: The metric name.
        db: Injected database session.

    Returns:
        Standardised success response with ``metric_name``, ``value``,
        and ``timestamp`` in ``data``.

    Raises:
        MetricNotFoundError (→ 404): When the metric does not exist.
        InvalidDataError (→ 422): When the metric has no datapoints yet.
    """
    dp = await datapoint_service.get_latest_value(db, metric_name=name)
    return success_response(
        LatestValueResponse(
            metric_name=name,
            value=float(dp.value),
            timestamp=dp.timestamp,
        ).model_dump()
    )


@router.post("/{name}/data", response_model=dict, status_code=201)
async def upload_datapoints(
    name: str,
    body: DatapointBatchCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Bulk-upload datapoints to a metric.

    Args:
        name: The target metric name.
        body: ``DatapointBatchCreate`` payload.
        db: Injected database session.

    Returns:
        Standardised success response with the created datapoints in ``data``.

    Raises:
        MetricNotFoundError (→ 404): When the metric does not exist.
        InvalidDataError (→ 422): When any ``value`` is not finite.
    """
    records = await datapoint_service.create_datapoints(
        db,
        metric_name=name,
        datapoints=[d.model_dump() for d in body.datapoints],
    )
    return success_response(
        {
            "created": len(records),
            "items": [
                DatapointResponse.model_validate(r).model_dump() for r in records
            ],
        }
    )


@router.get("/{name}/data", response_model=dict)
async def query_datapoints(
    name: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    start: datetime | None = Query(None, description="Inclusive lower bound (UTC)"),
    end: datetime | None = Query(None, description="Inclusive upper bound (UTC)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(1000, ge=1, le=10000, description="Max records to return"),
) -> dict:
    """Query raw datapoints for a metric, optionally filtered by time range.

    Args:
        name: The metric name.
        db: Injected database session.
        start: Optional inclusive lower bound (UTC).
        end: Optional inclusive upper bound (UTC).
        skip: Offset for pagination.
        limit: Page size (capped at 10000).

    Returns:
        Standardised success response with ``items`` and ``total`` in ``data``.

    Raises:
        MetricNotFoundError (→ 404): When the metric does not exist.
    """
    items, total = await datapoint_service.get_datapoints(
        db,
        metric_name=name,
        start=start,
        end=end,
        skip=skip,
        limit=limit,
    )
    return success_response(
        DatapointListResponse(
            items=[DatapointResponse.model_validate(d) for d in items],
            total=total,
        ).model_dump()
    )
