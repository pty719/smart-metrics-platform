"""SQLAlchemy ORM model for the ``metrics`` table."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.datapoint import Datapoint
    from app.models.task import Task


class Metric(Base):
    """Represents a named time-series metric definition.

    Attributes:
        id: Auto-incremented primary key.
        name: Unique, human-readable metric identifier (e.g. "daily_users").
        description: Optional long description.
        unit: Optional unit label (e.g. "人", "ms", "℃").
        created_at: Record creation timestamp (set by DB).
        updated_at: Record last-update timestamp (set by DB).
        datapoints: All data points belonging to this metric.
        tasks: All forecast / analysis tasks for this metric.
    """

    __tablename__ = "metrics"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False
    )
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    datapoints: Mapped[List["Datapoint"]] = relationship(
        back_populates="metric",
        cascade="all, delete-orphan",
        lazy="select",
    )
    tasks: Mapped[List["Task"]] = relationship(
        back_populates="metric",
        lazy="select",
    )
