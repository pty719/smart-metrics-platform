"""Redis async client singleton.

The client is created lazily on first access and reused for the lifetime
of the application process.
"""
from __future__ import annotations

from redis.asyncio import Redis

from app.config import settings

_redis_client: Redis | None = None


def get_redis() -> Redis:
    """Return (and lazily create) the global Redis client.

    Returns:
        An async Redis client configured from ``settings``.
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


async def close_redis() -> None:
    """Close the Redis connection gracefully on application shutdown."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
