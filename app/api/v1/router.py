"""API v1 router — aggregates all endpoint sub-routers."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import forecast, health, metrics, stats

router = APIRouter()

router.include_router(health.router)
router.include_router(metrics.router)
router.include_router(stats.router)
router.include_router(forecast.router)

