"""Integration tests for the metrics management API.

Uses the real test database and an async HTTP test client (httpx).
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestCreateMetric:
    """POST /api/v1/metrics"""

    async def test_create_metric_success(
        self, client: AsyncClient, api_key: str
    ) -> None:
        """A valid payload should return 201 and the created metric."""
        resp = await client.post(
            "/api/v1/metrics",
            json={"name": "daily_active_users", "unit": "人", "description": "日活"},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["code"] == 0
        data = body["data"]
        assert data["name"] == "daily_active_users"
        assert data["unit"] == "人"
        assert "id" in data

    async def test_create_duplicate_fails(
        self, client: AsyncClient, api_key: str, existing_metric: dict
    ) -> None:
        """Creating a metric with a duplicate name should return 409."""
        resp = await client.post(
            "/api/v1/metrics",
            json={"name": existing_metric["name"]},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert resp.status_code == 409
        assert "已存在" in resp.json()["message"]

    async def test_create_invalid_name_fails(
        self, client: AsyncClient, api_key: str
    ) -> None:
        """Names that don't match the pattern should return 422."""
        resp = await client.post(
            "/api/v1/metrics",
            json={"name": "123bad"},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert resp.status_code == 422

    async def test_create_no_api_key_fails(self, client: AsyncClient) -> None:
        """Missing API key should return 401."""
        resp = await client.post(
            "/api/v1/metrics",
            json={"name": "no_auth_test"},
        )
        assert resp.status_code == 401


class TestListMetrics:
    """GET /api/v1/metrics"""

    async def test_list_metrics_returns_all(
        self, client: AsyncClient, api_key: str, existing_metric: dict
    ) -> None:
        """Should return a paginated list containing the seeded metric."""
        resp = await client.get(
            "/api/v1/metrics",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        data = body["data"]
        assert data["total"] >= 1
        names = [m["name"] for m in data["items"]]
        assert existing_metric["name"] in names

    async def test_list_metrics_pagination(
        self, client: AsyncClient, api_key: str
    ) -> None:
        """skip and limit should control the result window."""
        # Create a few metrics first
        for i in range(5):
            await client.post(
                "/api/v1/metrics",
                json={"name": f"pagination_test_{i}"},
                headers={"Authorization": f"Bearer {api_key}"},
            )
        resp = await client.get(
            "/api/v1/metrics?skip=0&limit=2",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["items"]) <= 2


class TestGetMetric:
    """GET /api/v1/metrics/{name}"""

    async def test_get_existing_metric(
        self, client: AsyncClient, api_key: str, existing_metric: dict
    ) -> None:
        """Fetching an existing metric by name should return 200."""
        resp = await client.get(
            f"/api/v1/metrics/{existing_metric['name']}",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["name"] == existing_metric["name"]

    async def test_get_nonexistent_metric_returns_404(
        self, client: AsyncClient, api_key: str
    ) -> None:
        """Fetching a non-existent metric should return 404."""
        resp = await client.get(
            "/api/v1/metrics/does_not_exist",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert resp.status_code == 404


class TestDeleteMetric:
    """DELETE /api/v1/metrics/{name}"""

    async def test_delete_metric_success(
        self, client: AsyncClient, api_key: str
    ) -> None:
        """Deleting an existing metric should return 204."""
        # Create first
        name = "to_delete"
        await client.post(
            "/api/v1/metrics",
            json={"name": name},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        # Delete
        resp = await client.delete(
            f"/api/v1/metrics/{name}",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert resp.status_code == 204
        # Confirm gone
        resp2 = await client.get(
            f"/api/v1/metrics/{name}",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert resp2.status_code == 404

    async def test_delete_nonexistent_returns_404(
        self, client: AsyncClient, api_key: str
    ) -> None:
        """Deleting a non-existent metric should return 404."""
        resp = await client.delete(
            "/api/v1/metrics/does_not_exist",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert resp.status_code == 404


class TestUploadDatapoints:
    """POST /api/v1/metrics/{name}/data"""

    async def test_upload_single_datapoint(
        self, client: AsyncClient, api_key: str, existing_metric: dict
    ) -> None:
        """Uploading a single datapoint should return 201."""
        resp = await client.post(
            f"/api/v1/metrics/{existing_metric['name']}/data",
            json={"datapoints": [{"value": 42.0}]},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["code"] == 0
        data = body["data"]
        assert data["created"] == 1

    async def test_upload_multiple_datapoints(
        self, client: AsyncClient, api_key: str, existing_metric: dict
    ) -> None:
        """Uploading multiple datapoints should return 201."""
        resp = await client.post(
            f"/api/v1/metrics/{existing_metric['name']}/data",
            json={"datapoints": [{"value": 1.0}, {"value": 2.0}, {"value": 3.0}]},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert resp.status_code == 201
        assert resp.json()["data"]["created"] == 3

    async def test_upload_to_nonexistent_metric_returns_404(
        self, client: AsyncClient, api_key: str
    ) -> None:
        """Uploading to a non-existent metric should return 404."""
        resp = await client.post(
            "/api/v1/metrics/does_not_exist/data",
            json={"datapoints": [{"value": 1.0}]},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert resp.status_code == 404


class TestGetLatestValue:
    """GET /api/v1/metrics/{name}/latest"""

    async def test_get_latest_value(
        self, client: AsyncClient, api_key: str, existing_metric: dict
    ) -> None:
        """After uploading datapoints, latest should return the last one."""
        # Upload two points
        await client.post(
            f"/api/v1/metrics/{existing_metric['name']}/data",
            json={"datapoints": [{"value": 10.0}, {"value": 99.0}]},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        resp = await client.get(
            f"/api/v1/metrics/{existing_metric['name']}/latest",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["metric_name"] == existing_metric["name"]
        assert data["value"] == 99.0

    async def test_get_latest_no_data_returns_422(
        self, client: AsyncClient, api_key: str
    ) -> None:
        """If a metric has no datapoints, latest should return 422."""
        name = "no_data_metric"
        await client.post(
            "/api/v1/metrics",
            json={"name": name},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        resp = await client.get(
            f"/api/v1/metrics/{name}/latest",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert resp.status_code == 422


class TestQueryDatapoints:
    """GET /api/v1/metrics/{name}/data"""

    async def test_query_datapoints_returns_all(
        self, client: AsyncClient, api_key: str, existing_metric: dict
    ) -> None:
        """Querying without filters should return all datapoints."""
        # Upload some data
        await client.post(
            f"/api/v1/metrics/{existing_metric['name']}/data",
            json={"datapoints": [{"value": 1.0}, {"value": 2.0}]},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        resp = await client.get(
            f"/api/v1/metrics/{existing_metric['name']}/data",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] >= 2

    async def test_query_nonexistent_metric_returns_404(
        self, client: AsyncClient, api_key: str
    ) -> None:
        """Querying a non-existent metric should return 404."""
        resp = await client.get(
            "/api/v1/metrics/does_not_exist/data",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert resp.status_code == 404
