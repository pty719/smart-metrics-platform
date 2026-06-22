"""Unit tests for cache_service.

All tests mock the Redis client so no real Redis instance is required.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import cache_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_redis(get_return: str | None = None) -> AsyncMock:
    """Return a minimal fake async Redis client."""
    r = AsyncMock()
    r.get = AsyncMock(return_value=get_return)
    r.set = AsyncMock(return_value=True)
    r.unlink = AsyncMock(return_value=1)
    # scan returns (cursor, [keys]) — simulate a single page with no more results
    r.scan = AsyncMock(return_value=(0, []))
    return r


# ---------------------------------------------------------------------------
# Key helper tests (pure, no Redis)
# ---------------------------------------------------------------------------


class TestKeyHelpers:
    def test_stats_key_format(self) -> None:
        assert cache_service.stats_key("cpu_usage") == "stats:cpu_usage:stats"

    def test_anomalies_key_format(self) -> None:
        assert cache_service.anomalies_key("cpu_usage") == "stats:cpu_usage:anomalies"

    def test_moving_average_key_format(self) -> None:
        assert (
            cache_service.moving_average_key("cpu_usage", 7)
            == "stats:cpu_usage:ma_7"
        )

    def test_keys_are_unique_across_metrics(self) -> None:
        assert cache_service.stats_key("m1") != cache_service.stats_key("m2")

    def test_ma_keys_differ_by_window(self) -> None:
        assert cache_service.moving_average_key("m", 7) != cache_service.moving_average_key(
            "m", 14
        )


# ---------------------------------------------------------------------------
# get_cached / set_cached
# ---------------------------------------------------------------------------


class TestGetSetCached:
    @pytest.mark.asyncio
    async def test_get_cached_miss(self) -> None:
        """Cache miss returns None."""
        redis = _make_redis(get_return=None)
        result = await cache_service.get_cached("some:key", redis=redis)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_cached_hit(self) -> None:
        """Cache hit deserialises JSON."""
        payload = {"mean": 42.0, "count": 10}
        redis = _make_redis(get_return=json.dumps(payload))
        result = await cache_service.get_cached("some:key", redis=redis)
        assert result == payload

    @pytest.mark.asyncio
    async def test_set_cached_calls_redis_set(self) -> None:
        """set_cached must call redis.set with correct key and TTL."""
        redis = _make_redis()
        await cache_service.set_cached("k", {"x": 1}, ttl=300, redis=redis)
        redis.set.assert_called_once()
        call_args = redis.set.call_args
        # Positional: key, serialised_value; keyword: ex=ttl
        assert call_args[0][0] == "k"
        assert json.loads(call_args[0][1]) == {"x": 1}
        assert call_args[1]["ex"] == 300

    @pytest.mark.asyncio
    async def test_set_cached_serialises_datetime(self) -> None:
        """datetime values in the payload should be serialised to ISO strings."""
        redis = _make_redis()
        ts = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        await cache_service.set_cached("k", {"ts": ts}, ttl=60, redis=redis)
        raw = redis.set.call_args[0][1]
        data = json.loads(raw)
        assert data["ts"] == ts.isoformat()


# ---------------------------------------------------------------------------
# Convenience wrappers (stats / anomalies / moving average)
# ---------------------------------------------------------------------------


class TestConvenienceWrappers:
    @pytest.mark.asyncio
    async def test_get_stats_cache_miss(self) -> None:
        redis = _make_redis()
        assert await cache_service.get_stats_cache("m", redis=redis) is None

    @pytest.mark.asyncio
    async def test_set_stats_cache_uses_correct_ttl(self) -> None:
        """Stats cache must use CACHE_TTL_STATS from settings."""
        redis = _make_redis()
        with patch("app.services.cache_service.settings") as mock_settings:
            mock_settings.CACHE_TTL_STATS = 300
            await cache_service.set_stats_cache("m", {"count": 1}, redis=redis)
        redis.set.assert_called_once()
        assert redis.set.call_args[1]["ex"] == 300

    @pytest.mark.asyncio
    async def test_set_anomalies_cache_uses_correct_ttl(self) -> None:
        redis = _make_redis()
        with patch("app.services.cache_service.settings") as mock_settings:
            mock_settings.CACHE_TTL_ANOMALIES = 60
            await cache_service.set_anomalies_cache("m", {"anomaly_count": 0}, redis=redis)
        assert redis.set.call_args[1]["ex"] == 60

    @pytest.mark.asyncio
    async def test_set_ma_cache_uses_correct_ttl(self) -> None:
        redis = _make_redis()
        with patch("app.services.cache_service.settings") as mock_settings:
            mock_settings.CACHE_TTL_MA = 600
            await cache_service.set_moving_average_cache("m", 7, {"window": 7}, redis=redis)
        assert redis.set.call_args[1]["ex"] == 600


# ---------------------------------------------------------------------------
# invalidate_metric_cache
# ---------------------------------------------------------------------------


class TestInvalidateMetricCache:
    @pytest.mark.asyncio
    async def test_no_keys_returns_zero(self) -> None:
        """When no cached keys exist, returns 0 deleted."""
        redis = _make_redis()
        redis.scan = AsyncMock(return_value=(0, []))
        deleted = await cache_service.invalidate_metric_cache("no_such_metric", redis=redis)
        assert deleted == 0

    @pytest.mark.asyncio
    async def test_deletes_all_matching_keys(self) -> None:
        """Should call unlink with all matching keys."""
        keys = [
            b"stats:cpu:stats",
            b"stats:cpu:anomalies",
            b"stats:cpu:ma_7",
        ]
        redis = _make_redis()
        redis.scan = AsyncMock(return_value=(0, keys))

        deleted = await cache_service.invalidate_metric_cache("cpu", redis=redis)

        redis.unlink.assert_called_once_with(*keys)
        assert deleted == 3

    @pytest.mark.asyncio
    async def test_handles_multi_page_scan(self) -> None:
        """scan cursor != 0 means more pages; all pages should be processed."""
        page1_keys = [b"stats:m:stats", b"stats:m:anomalies"]
        page2_keys = [b"stats:m:ma_7"]

        call_count = 0

        async def _scan(cursor, match, count):
            nonlocal call_count
            call_count += 1
            if cursor == 0:
                return (42, page1_keys)  # first page, non-zero cursor = more pages
            return (0, page2_keys)  # second page, cursor=0 = done

        redis = _make_redis()
        redis.scan = _scan

        deleted = await cache_service.invalidate_metric_cache("m", redis=redis)

        assert deleted == 3
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_invalidate_stats_only(self) -> None:
        """invalidate_stats_only should call unlink with the stats key only."""
        redis = _make_redis()
        await cache_service.invalidate_stats_only("m", redis=redis)
        redis.unlink.assert_called_once_with(cache_service.stats_key("m"))
