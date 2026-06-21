"""Pydantic schemas for the forecast API."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ForecastSubmitRequest(BaseModel):
    """Request body for ``POST /api/v1/metrics/{name}/forecast``."""

    steps: int = Field(
        default=10, ge=1, le=100,
        description="Number of future points to forecast (1–100)",
    )
    conf_level: float = Field(
        default=0.95, ge=0.5, le=0.999,
        description="Confidence level for the prediction interval (0.5–0.999)",
    )

    model_config = {"json_schema_extra__": {"example": {"steps": 10, "conf_level": 0.95}}}


class ForecastHistoryPoint(BaseModel):
    timestamp: str
    value: float


class ForecastPoint(BaseModel):
    timestamp: str
    value: float
    lower_bound: float
    upper_bound: float


class ForecastResult(BaseModel):
    """Forecast result returned in ``Task.result`` and in the API response."""

    metric_name: str
    model: str
    conf_level: float
    slope: float
    intercept: float
    r_squared: float
    steps: int
    history: list[ForecastHistoryPoint]
    forecast: list[ForecastPoint]


class TaskStatusResponse(BaseModel):
    """Response for ``GET /api/v1/tasks/{task_id}``."""

    id: str
    metric_name: str
    task_type: str
    status: str
    parameters: Optional[dict] = None
    result: Optional[ForecastResult] = None
    error_message: Optional[str] = None
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
