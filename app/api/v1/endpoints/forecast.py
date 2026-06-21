"""API endpoints for async forecast (Celery).

Endpoints:
- POST /api/v1/metrics/{name}/forecast — submit a forecast task
- GET  /api/v1/tasks/{task_id}        — poll task status / result
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, verify_api_key
from app.api.responses import success_response
from app.api.v1.schemas.forecast import (
    ForecastSubmitRequest,
    TaskStatusResponse,
)
from app.core.celery_app import celery_app
from app.core.exceptions import InvalidDataError, MetricNotFoundError, TaskNotFoundError
from app.models.datapoint import Datapoint
from app.models.metric import Metric
from app.models.task import Task, TaskStatus, TaskType

router = APIRouter(prefix="/metrics", dependencies=[Depends(verify_api_key)])


# ---------------------------------------------------------------------------
# POST /api/v1/metrics/{name}/forecast
# ---------------------------------------------------------------------------


@router.post("/{name}/forecast", response_model=dict, status_code=202)
async def submit_forecast(
    name: str,
    body: ForecastSubmitRequest | None = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> dict:
    """Submit an async forecast task for *name*.

    Returns HTTP 202 with a ``task_id`` immediately.  The actual forecast
    runs in a Celery worker; poll ``GET /api/v1/tasks/{task_id}`` for
    results.

    Args:
        name: Metric name.
        body: Optional ``steps`` and ``conf_level``.
        db: Injected database session.

    Returns:
        Standardised success response with ``task_id`` in ``data``.

    Raises:
        MetricNotFoundError (→ 404): When the metric does not exist.
        InvalidDataError (→ 422): When the metric has fewer than 2 points.
    """
    if body is None:
        body = ForecastSubmitRequest()

    # Verify metric exists and has enough data
    metric = await db.scalar(select(Metric).where(Metric.name == name))
    if metric is None:
        raise MetricNotFoundError(name)

    from sqlalchemy import func

    count = await db.scalar(
        select(func.count(Datapoint.id)).where(Datapoint.metric_id == metric.id)
    )
    if count is None or count < 2:
        raise InvalidDataError(
            f"Metric '{name}' needs at least 2 data points for forecasting, "
            f"got {count or 0}"
        )

    # Create Task DB row
    task_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    task = Task(
        id=task_id,
        metric_id=metric.id,
        task_type=TaskType.FORECAST,
        status=TaskStatus.PENDING,
        parameters={"steps": body.steps, "conf_level": body.conf_level},
        created_at=now,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)

    # Dispatch Celery task (fire-and-forget)
    celery_app.send_task(
        "app.tasks.forecast_tasks.forecast_task",
        args=[task_id, metric.id, body.steps, body.conf_level],
    )

    await db.commit()

    return success_response(
        {
            "task_id": task_id,
            "metric_name": name,
            "status": TaskStatus.PENDING.value,
            "poll_url": f"/api/v1/tasks/{task_id}",
        },
        message="forecast task submitted",
    )


# ---------------------------------------------------------------------------
# GET /api/v1/tasks/{task_id}
# ---------------------------------------------------------------------------


@router.get("/tasks/{task_id}", response_model=dict)
async def get_task_status(
    task_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Return the status and (if completed) result of a forecast task.

    Args:
        task_id: UUID of the task.
        db: Injected database session.

    Returns:
        Standardised success response with task details in ``data``.

    Raises:
        TaskNotFoundError (→ 404): When no task with *task_id* exists.
    """
    task = await db.get(Task, task_id)
    if task is None:
        raise TaskNotFoundError(task_id)

    # Load metric name for the response
    metric = await db.get(Metric, task.metric_id)
    metric_name = metric.name if metric else "unknown"

    data: dict = {
        "task_id": task.id,
        "metric_name": metric_name,
        "task_type": task.task_type.value,
        "status": task.status.value,
        "parameters": task.parameters,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }

    if task.status == TaskStatus.SUCCESS:
        data["result"] = task.result
    elif task.status == TaskStatus.FAILURE:
        data["error_message"] = task.error_message

    return success_response(data)
