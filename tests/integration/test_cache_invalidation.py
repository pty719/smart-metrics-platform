"""Integration tests — cache invalidation on data upload.

Verifies that when new datapoints are written via
``POST /api/v1/metrics/{name}/data``, the cache service is called to
invalidate all related Redis entries for that metric.

The real Redis client is replaced with an AsyncMock so the suite can run
without a live Redis instance.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, call, patch

import pytest
from httpx import AsyncClient

from app.services.cache_service import (
    anomalies_key,
    moving_average_key,
    stats_key,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_redis_mock() -> AsyncMock:
    """Redis mock: always cache-miss on reads, silent on writes."""
    m = AsyncMock()
    m.get.return_value = None
    m.set.return_value = True
    m.unlink.return_value = 0
    m.scan.return_value = (0, [])
    return m


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCacheInvalidationOnUpload:
    """Uploading data must trigger cache invalidation for that metric."""

    async def test_invalidate_called_on_data_upload(
        self,
        client: AsyncClient,
        api_key: str,
    ) -> None:
        """``cache_service.invalidate_metric_cache`` must be called after upload."""
        metric_name = "ci_test_metric"
        auth = {"Authorization": f"Bearer {api_key}"}

        redis_mock = _make_redis_mock()

        with patch("app.services.cache_service.get_redis", return_value=redis_mock):
            # Create metric
            await client.post(
                "/api/v1/metrics",
                json={"name": metric_name, "unit": "ms"},
                headers=auth,
            )

            # Upload data — this should trigger invalidation
            resp = await client.post(
                f"/api/v1/metrics/{metric_name}/data",
                json={"datapoints": [{"value": v} for v in [1, 2, 3]]},
                headers=auth,
            )
            assert resp.status_code == 201

            # invalidation path uses scan + unlink
            # scan was called at least once searching for stats:ci_test_metric:*
            redis_mock.scan.assert_called()
            first_scan_call = redis_mock.scan.call_args_list[0]
            assert metric_name in first_scan_call[1]["match"]

    async def test_stats_reflect_new_data_after_upload(
        self,
        client: AsyncClient,
        api_key: str,
    ) -> None:
        """After upload, a fresh stats query must hit the DB (cache invalidated).

        We simulate this by pre-loading a stale value in the mock cache,
        uploading new data (which should purge it), then confirming the
        cache is cleared so the next read goes to the DB.
        """
        metric_name = "ci_fresh_stats"
        auth = {"Authorization": f"Bearer {api_key}"}

        stale_cache: dict = {}  # shared dict simulates Redis storage

        async def fake_get(key: str) -> str | None:
            return stale_cache.get(key)

        async def fake_set(key: str, value: str, ex: int | None = None) -> None:
            stale_cache[key] = value

        async def fake_scan(cursor: int, match: str, count: int):
            matching = [k for k in stale_cache if _glob_match(match, k)]
            return (0, matching)

        async def fake_unlink(*keys: str) -> int:
            removed = 0
            for k in keys:
                if k in stale_cache:
                    del stale_cache[k]
                    removed += 1
            return removed

        redis_mock = AsyncMock()
        redis_mock.get = fake_get
        redis_mock.set = fake_set
        redis_mock.scan = fake_scan
        redis_mock.unlink = fake_unlink

        with patch("app.services.cache_service.get_redis", return_value=redis_mock):
            # Create metric and upload first batch
            await client.post(
                "/api/v1/metrics",
                json={"name": metric_name, "unit": "count"},
                headers=auth,
            )
            await client.post(
                f"/api/v1/metrics/{metric_name}/data",
                json={"datapoints": [{"value": 10}]},
                headers=auth,
            )

            # Query stats — populates the cache
            resp1 = await client.get(
                f"/api/v1/metrics/{metric_name}/stats",
                headers=auth,
            )
            assert resp1.status_code == 200
            data1 = resp1.json()["data"]
            assert data1["count"] == 1

            # Confirm a stats entry is now cached
            assert stats_key(metric_name) in stale_cache

            # Upload second batch — must invalidate the cache
            await client.post(
                f"/api/v1/metrics/{metric_name}/data",
                json={"datapoints": [{"value": 20}, {"value": 30}]},
                headers=auth,
            )

            # The stats cache entry should have been evicted
            assert stats_key(metric_name) not in stale_cache

            # Re-query stats — DB is hit fresh, returns updated count
            resp2 = await client.get(
                f"/api/v1/metrics/{metric_name}/stats",
                headers=auth,
            )
            assert resp2.status_code == 200
            data2 = resp2.json()["data"]
            assert data2["count"] == 3  # 1 + 2 new points
            assert data2["max"] == 30.0


# ---------------------------------------------------------------------------
# Mini glob helper (for the fake scan above)
# ---------------------------------------------------------------------------


def _glob_match(pattern: str, text: str) -> bool:
    """Very simple ``*``-only glob matching (sufficient for our key patterns)."""
    if pattern.endswith("*"):
        return text.startswith(pattern[:-1])
    return text == pattern
