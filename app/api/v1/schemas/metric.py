"""Pydantic schemas for the Metric API."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class MetricCreate(BaseModel):
    """Request body for POST /api/v1/metrics."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$",
        description=(
            "Unique metric identifier. "
            "Must start with a letter or underscore, "
            "followed by letters, digits, or underscores."
        ),
    )
    unit: Optional[str] = Field(
        None,
        max_length=50,
        description="Optional unit label, e.g. '人', 'ms', '℃'.",
    )
    description: Optional[str] = Field(
        None,
        max_length=500,
        description="Optional human-readable description.",
    )


class MetricResponse(BaseModel):
    """Response body for single metric endpoints."""

    id: int
    name: str
    description: Optional[str] = None
    unit: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MetricListResponse(BaseModel):
    """Wrapper for a list of metrics."""

    items: list[MetricResponse]
    total: int


class DatapointCreate(BaseModel):
    """Request body for uploading a single datapoint."""

    value: float = Field(..., description="The numeric value of this data point.")
    timestamp: Optional[datetime] = Field(
        None,
        description=(
            "Optional timestamp. " "Defaults to server time if omitted."
        ),
    )

    @field_validator("value")
    @classmethod
    def value_not_nan(cls, v: float) -> float:
        import math

        if math.isnan(v) or math.isinf(v):
            raise ValueError("value must be a finite number")
        return v


class DatapointBatchCreate(BaseModel):
    """Request body for uploading multiple datapoints."""

    datapoints: list[DatapointCreate] = Field(
        ...,
        min_length=1,
        description="List of data points to upload.",
    )


class DatapointResponse(BaseModel):
    """Response body for a single datapoint."""

    id: int
    metric_id: int
    value: float
    timestamp: datetime

    model_config = {"from_attributes": True}


class DatapointListResponse(BaseModel):
    """Wrapper for a list of datapoints."""

    items: list[DatapointResponse]
    total: int


class LatestValueResponse(BaseModel):
    """Response body for the latest value endpoint."""

    metric_name: str
    value: float
    timestamp: datetime
