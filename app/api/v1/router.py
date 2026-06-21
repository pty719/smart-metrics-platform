"""API v1 router — aggregates all endpoint sub-routers."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import health

router = APIRouter()

router.include_router(health.router)
