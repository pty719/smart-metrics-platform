"""Integration tests for the forecast API.

Uses the real test database and an async HTTP test client (httpx).
Celery ``send_task`` is mocked so that no external worker is required.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient


# ── Helpers ─────────────────────────────────────────────────────────────


async def _create_metric_with_data(
    client: AsyncClient,
    api_key: str,
    name: str = "forecast_test_metric",
    values: list[float] | None = None,
) -> str:
    """Create a metric and upload datapoints; return the metric name."""
    if values is None:
        values = [10.0, 20.0, 30.0, 40.0, 50.0]

    await client.post(
        "/api/v1/metrics",
        json={"name": name, "unit": "℃"},
        headers={"Authorization": f"Bearer {api_key}"},
    )
    await client.post(
        f"/api/v1/metrics/{name}/data",
        json={"datapoints": [{"value": v} for v in values]},
        headers={"Authorization": f"Bearer {api_key}"},
    )
    return name


# ── POST /metrics/{name}/forecast ──────────────────────────────────────


class TestSubmitForecast:
    """POST /api/v1/metrics/{name}/forecast"""

    @patch("app.api.v1.endpoints.forecast.celery_app")
    async def test_submit_returns_202_and_task_id(
        self, mock_celery: MagicMock, client: AsyncClient, api_key: str,
    ) -> None:
        """Submitting a forecast should return HTTP 202 with a task_id."""
        name = await _create_metric_with_data(client, api_key)

        # Mock send_task to do nothing
        mock_celery.send_task = MagicMock()

        resp = await client.post(
            f"/api/v1/metrics/{name}/forecast",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert resp.status_code == 202
        body = resp.json()
        assert body["code"] == 0
        data = body["data"]
        assert "task_id" in data
        assert data["status"] == "pending"
        assert "poll_url" in data

    @patch("app.api.v1.endpoints.forecast.celery_app")
    async def test_submit_with_custom_steps(
        self, mock_celery: MagicMock, client: AsyncClient, api_key: str,
    ) -> None:
        """``steps`` parameter should be accepted in the request body."""
        name = await _create_metric_with_data(client, api_key)
        mock_celery.send_task = MagicMock()

        resp = await client.post(
            f"/api/v1/metrics/{name}/forecast",
            json={"steps": 20, "conf_level": 0.90},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert resp.status_code == 202

    async def test_nonexistent_metric_returns_404(
        self, client: AsyncClient, api_key: str,
    ) -> None:
        """Submitting for a non-existent metric should return 404."""
        resp = await client.post(
            "/api/v1/metrics/no_such/forecast",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert resp.status_code == 404

    @patch("app.api.v1.endpoints.forecast.celery_app")
    async def test_insufficient_data_returns_422(
        self, mock_celery: MagicMock, client: AsyncClient, api_key: str,
    ) -> None:
        """Metric with fewer than 2 datapoints should return 422."""
        name = await _create_metric_with_data(client, api_key, values=[1.0])

        mock_celery.send_task = MagicMock()

        resp = await client.post(
            f"/api/v1/metrics/{name}/forecast",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        # The endpoint checks count before submitting, so it returns 422
        assert resp.status_code == 422

    async def test_no_api_key_returns_401(
        self, client: AsyncClient, api_key: str,
    ) -> None:
        """Missing API key should return 401."""
        resp = await client.post(
            "/api/v1/metrics/any_metric/forecast",
        )
        assert resp.status_code == 401


# ── GET /tasks/{task_id} ───────────────────────────────────────────────


class TestGetTaskStatus:
    """GET /api/v1/tasks/{task_id}"""

    @patch("app.api.v1.endpoints.forecast.celery_app")
    async def test_returns_task_status(
        self, mock_celery: MagicMock, client: AsyncClient, api_key: str,
    ) -> None:
        """After submitting, the task should be pollable."""
        name = await _create_metric_with_data(client, api_key)
        mock_celery.send_task = MagicMock()

        # Submit
        submit_resp = await client.post(
            f"/api/v1/metrics/{name}/forecast",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        task_id = submit_resp.json()["data"]["task_id"]

        # Poll
        resp = await client.get(
            f"/api/v1/metrics/tasks/{task_id}",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        data = body["data"]
        assert data["task_id"] == task_id
        assert data["status"] in ("pending", "started", "success", "failure")

    async def test_nonexistent_task_returns_404(
        self, client: AsyncClient, api_key: str,
    ) -> None:
        """Polling a non-existent task ID should return 404."""
        resp = await client.get(
            "/api/v1/metrics/tasks/00000000-0000-0000-0000-000000000000",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert resp.status_code == 404
