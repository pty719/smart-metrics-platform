"""Celery application instance.

Import ``celery_app`` to send tasks or use it in worker startup.
"""
from __future__ import annotations

from celery import Celery

from app.config import settings

celery_app = Celery(
    "metrics_platform",
    broker=settings.CELERY_BROKER_URL or settings.REDIS_URL,
    backend=settings.CELERY_RESULT_BACKEND or settings.REDIS_URL,
    include=["app.tasks.forecast_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,       # hard limit: 5 minutes
    task_soft_time_limit=280,  # soft limit: warn at 4m40s
    broker_connection_retry_on_startup=True,
)
