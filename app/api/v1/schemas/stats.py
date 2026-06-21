"""Pydantic schemas for the Statistics API."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


# ── /stats ────────────────────────────────────────────────────────────────


class StatsResponse(BaseModel):
    """Response body for GET /metrics/{name}/stats."""

    metric_name: str
    count: int
    mean: float
    min: float
    max: float
    std_dev: Optional[float] = None
    median: float


# ── /anomalies ───────────────────────────────────────────────────────────


class AnomalyItem(BaseModel):
    """A single anomaly data point."""

    id: int
    value: float
    timestamp: datetime


class AnomaliesResponse(BaseModel):
    """Response body for GET /metrics/{name}/anomalies."""

    metric_name: str
    mean: float
    std_dev: Optional[float] = None
    threshold_lower: float
    threshold_upper: float
    anomaly_count: int
    anomalies: list[AnomalyItem]


# ── /moving-average ──────────────────────────────────────────────────────


class MovingAveragePoint(BaseModel):
    """A single point in the moving-average series."""

    timestamp: datetime
    value: float
    moving_average: float


class MovingAverageResponse(BaseModel):
    """Response body for GET /metrics/{name}/moving-average."""

    metric_name: str
    window: int
    data_points: list[MovingAveragePoint]
