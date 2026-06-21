"""Health check endpoint.

GET /api/v1/health  — no authentication required.

Checks connectivity to PostgreSQL and Redis and returns an aggregated
status so that container orchestration tools (Docker, Kubernetes) can
determine whether the service is ready to accept traffic.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, get_redis

router = APIRouter(tags=["System"])


@router.get(
    "/health",
    summary="Health Check",
    description=(
        "Returns the health status of the API and its dependencies "
        "(PostgreSQL and Redis). No authentication required."
    ),
    response_model=None,
)
async def health_check(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> dict:
    """Check connectivity to all backend dependencies.

    Returns:
        Dict with overall status and per-component status.

        Example::

            {
                "status": "ok",
                "components": {
                    "database": "ok",
                    "redis": "ok"
                }
            }
    """
    db_ok = False
    redis_ok = False

    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    try:
        await redis.ping()
        redis_ok = True
    except Exception:
        pass

    overall = "ok" if (db_ok and redis_ok) else "degraded"

    return {
        "status": overall,
        "components": {
            "database": "ok" if db_ok else "error",
            "redis": "ok" if redis_ok else "error",
        },
    }
