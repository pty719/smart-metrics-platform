"""SQLAlchemy ORM model for the ``datapoints`` table."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.metric import Metric


class Datapoint(Base):
    """A single timestamped value belonging to a metric.

    Attributes:
        id: Auto-incremented primary key.
        metric_id: Foreign key to the parent ``Metric``.
        timestamp: The point-in-time this measurement was taken.
        value: The numeric measurement value (high-precision decimal).
        created_at: DB-side insert timestamp.
        metric: Back-reference to the parent ``Metric`` instance.
    """

    __tablename__ = "datapoints"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    metric_id: Mapped[int] = mapped_column(
        ForeignKey("metrics.id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    value: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    metric: Mapped["Metric"] = relationship(back_populates="datapoints")

    __table_args__ = (
        # Speeds up the most common query pattern: WHERE metric_id = ? AND timestamp BETWEEN ...
        Index("idx_metric_timestamp", "metric_id", "timestamp"),
    )
