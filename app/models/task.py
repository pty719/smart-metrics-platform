"""SQLAlchemy ORM model for the ``tasks`` table (async forecast / batch jobs)."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Enum, ForeignKey, Index, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.metric import Metric


class TaskStatus(str, enum.Enum):
    """Lifecycle states of an async task."""

    PENDING = "pending"
    STARTED = "started"
    SUCCESS = "success"
    FAILURE = "failure"


class TaskType(str, enum.Enum):
    """Supported async task types."""

    FORECAST = "forecast"
    BATCH_ANALYSIS = "batch_analysis"


class Task(Base):
    """An async job (e.g. forecast) submitted by a client.

    Attributes:
        id: UUID string (set by the application, not the DB).
        metric_id: The metric this task operates on.
        task_type: Which kind of computation to run.
        status: Current lifecycle state.
        parameters: JSON blob with task-specific inputs (e.g. steps, algorithm).
        result: JSON blob written by the worker on success.
        error_message: Short description written by the worker on failure.
        celery_task_id: ID assigned by Celery (for status polling if needed).
        created_at: When the task was submitted.
        started_at: When the Celery worker picked it up.
        completed_at: When the worker finished (success or failure).
        metric: Back-reference to the parent ``Metric``.
    """

    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUID
    metric_id: Mapped[int] = mapped_column(
        ForeignKey("metrics.id"), nullable=False
    )
    task_type: Mapped[TaskType] = mapped_column(Enum(TaskType), nullable=False)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), default=TaskStatus.PENDING, nullable=False
    )

    parameters: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    celery_task_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    metric: Mapped["Metric"] = relationship(back_populates="tasks")

    __table_args__ = (
        Index("idx_tasks_status", "status"),
        Index("idx_tasks_metric_created", "metric_id", "created_at"),
    )
