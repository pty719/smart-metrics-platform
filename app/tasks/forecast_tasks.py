"""Celery async forecast task definitions.

Phase 1 placeholder — actual forecast logic will be implemented in Phase 2.
"""
from __future__ import annotations

from app.core.celery_app import celery_app


@celery_app.task(bind=True, name="app.tasks.forecast_tasks.forecast_task")
def forecast_task(self, task_id: str, metric_id: int, steps: int) -> dict:  # type: ignore[override]
    """Run a linear forecast for *metric_id* and write results to the DB.

    This is a placeholder — the implementation will be added in Phase 2.

    Args:
        task_id: UUID of the ``Task`` record to update.
        metric_id: The metric to forecast.
        steps: Number of future time points to predict.

    Returns:
        Dict with ``task_id`` for Celery result tracking.
    """
    raise NotImplementedError("Forecast task will be implemented in Phase 2")
