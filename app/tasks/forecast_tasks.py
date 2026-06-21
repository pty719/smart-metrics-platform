"""Celery async forecast task definitions.

Phase 3 implementation — runs linear regression forecast and persists
the result to the ``tasks`` DB table.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from celery import Task
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.core.database import async_session_factory
from app.models.task import Task, TaskStatus
from app.services import forecast_service


class CallbackTask(Task):  # type: ignore[misc]
    """Base task with success/failure DB callbacks."""

    def on_success(self, retval: Any, task_id: str, args: Any, kwargs: Any) -> None:  # type: ignore[override]
        pass  # result is already persisted by run_forecast_task

    def on_failure(self, exc: Exception, task_id: str, args: Any, kwargs: Any, einfo: Any) -> None:  # type: ignore[override]
        """Mark the DB task row as FAILED when the Celery task errors out."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_mark_failure(args, exc))
        finally:
            loop.close()


async def _mark_failure(args: Any, exc: Exception) -> None:
    """Write error_message to the Task DB row."""
    if not args:
        return
    task_id = args[0] if len(args) > 0 else None
    if not task_id:
        return
    async with async_session_factory() as db:
        task = await db.get(Task, task_id)
        if task is None:
            return
        task.status = TaskStatus.FAILURE
        task.error_message = str(exc)[:1000]
        task.completed_at = datetime.now(timezone.utc)
        await db.commit()


@celery_app.task(bind=True, base=CallbackTask, name="app.tasks.forecast_tasks.forecast_task")  # type: ignore[misc]
def forecast_task(
    self,
    task_id: str,
    metric_id: int,
    steps: int,
    conf_level: float = 0.95,
) -> dict:
    """Run a linear forecast for *metric_id* and persist results.

    Args:
        task_id: UUID of the ``Task`` record to update.
        metric_id: The metric to forecast.
        steps: Number of future time points to predict.
        conf_level: Confidence level for the prediction interval.

    Returns:
        Dict with ``task_id`` and ``status`` for Celery result tracking.
    """
    # Celery workers are synchronous; run the async function in a new event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(
            forecast_service.run_forecast_task(
                async_session_factory,
                task_id,
                metric_id,
                steps,
                conf_level,
            )
        )
    except Exception as exc:
        # on_failure will be called by CallbackTask, but we re-raise
        raise
    finally:
        loop.close()

    return {"task_id": task_id, "status": "success"}
