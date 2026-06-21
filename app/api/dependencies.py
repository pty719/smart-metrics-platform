"""Shared FastAPI dependency functions.

Import these in endpoint files instead of the underlying core modules
so that the dependency graph stays clean and easy to override in tests.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db as _get_db
from app.core.redis_client import get_redis as _get_redis
from app.core.security import verify_api_key  # re-exported for convenience

__all__ = ["get_db", "get_redis", "verify_api_key"]


async def get_db(
    session: AsyncSession = Depends(_get_db),
) -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session (thin wrapper for overriding in tests)."""
    yield session


def get_redis() -> Redis:
    """Return the global Redis client (thin wrapper for overriding in tests)."""
    return _get_redis()
