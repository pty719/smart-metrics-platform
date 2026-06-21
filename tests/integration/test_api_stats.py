"""Integration tests for the statistics API.

Uses the real test database and an async HTTP test client (httpx).
Redis is mocked so that no external Redis instance is required.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


# ── Fixtures ────────────────────────────────────────────────────────


def _mock_redis() -> AsyncMock:
    """Mock Redis client — always cache-miss, silence set."""
    m = AsyncMock()
    m.get.return_value = None
    m.set.return_value = True
    return m


@pytest.fixture(autouse=True)
def _patch_redis():
    """Automatically patch ``get_redis`` for every test in this module."""
    mock = _mock_redis()
    with (
        patch("app.services.stats_service.get_redis", return_value=mock),
    ):
        yield


@pytest.fixture()
async def metric_with_data(client: AsyncClient, api_key: str) -> str:
    """Create a metric and upload sample data; return its name."""
    name = "int_test_metric"
    # Create metric
    await client.post(
        "/api/v1/metrics",
        json={"name": name, "unit": "℃"},
        headers={"Authorization": f"Bearer {api_key}"},
    )
    # Upload data: [10, 20, 30, 40, 100 (outlier)]
    await client.post(
        f"/api/v1/metrics/{name}/data",
        json={"datapoints": [{"value": v} for v in [10, 20, 30, 40, 100]]},
        headers={"Authorization": f"Bearer {api_key}"},
    )
    return name


# ── GET /metrics/{name}/stats ──────────────────────────────────────


class TestGetStats:
    """GET /api/v1/metrics/{name}/stats"""

    async def test_returns_stats(
        self, client: AsyncClient, api_key: str, metric_with_data: str
    ) -> None:
        resp = await client.get(
            f"/api/v1/metrics/{metric_with_data}/stats",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        data = body["data"]
        assert data["metric_name"] == metric_with_data
        assert data["count"] == 5
        assert "mean" in data
        assert "min" in data
        assert "max" in data
        assert "median" in data
        assert data["min"] == 10.0
        assert data["max"] == 100.0

    async def test_nonexistent_metric_returns_404(
        self, client: AsyncClient, api_key: str
    ) -> None:
        resp = await client.get(
            "/api/v1/metrics/no_such/stats",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert resp.status_code == 404

    async def test_no_api_key_returns_401(
        self, client: AsyncClient, metric_with_data: str
    ) -> None:
        resp = await client.get(
            f"/api/v1/metrics/{metric_with_data}/stats",
        )
        assert resp.status_code == 401


# ── GET /metrics/{name}/anomalies ─────────────────────────────────


class TestGetAnomalies:
    """GET /api/v1/metrics/{name}/anomalies"""

    async def test_detects_outlier(
        self, client: AsyncClient, api_key: str, metric_with_data: str
    ) -> None:
        resp = await client.get(
            f"/api/v1/metrics/{metric_with_data}/anomalies",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        # 100 is outside the IQR bounds and should be detected
        assert data["anomaly_count"] >= 1
        values = [a["value"] for a in data["anomalies"]]
        assert 100.0 in values

    async def test_nonexistent_metric_returns_404(
        self, client: AsyncClient, api_key: str
    ) -> None:
        resp = await client.get(
            "/api/v1/metrics/no_such/anomalies",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert resp.status_code == 404


# ── GET /metrics/{name}/moving-average ─────────────────────────────


class TestGetMovingAverage:
    """GET /api/v1/metrics/{name}/moving-average"""

    async def test_returns_moving_average(
        self, client: AsyncClient, api_key: str, metric_with_data: str
    ) -> None:
        resp = await client.get(
            f"/api/v1/metrics/{metric_with_data}/moving-average?window=2",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        data = body["data"]
        assert data["window"] == 2
        assert len(data["data_points"]) == 5

    async def test_default_window_is_7(
        self, client: AsyncClient, api_key: str, metric_with_data: str
    ) -> None:
        resp = await client.get(
            f"/api/v1/metrics/{metric_with_data}/moving-average",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["window"] == 7

    async def test_window_too_small_returns_422(
        self, client: AsyncClient, api_key: str, metric_with_data: str
    ) -> None:
        resp = await client.get(
            f"/api/v1/metrics/{metric_with_data}/moving-average?window=0",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert resp.status_code == 422

    async def test_nonexistent_metric_returns_404(
        self, client: AsyncClient, api_key: str
    ) -> None:
        resp = await client.get(
            "/api/v1/metrics/no_such/moving-average",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert resp.status_code == 404
