"""Integration tests for the health check endpoint."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestHealthCheck:
    """Tests for GET /api/v1/health."""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, client: AsyncClient):
        """Health endpoint should always return 200."""
        response = await client.get("/api/v1/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_health_response_shape(self, client: AsyncClient):
        """Response should contain 'status' and 'components' keys."""
        response = await client.get("/api/v1/health")
        data = response.json()
        assert "status" in data
        assert "components" in data
        assert "database" in data["components"]
        assert "redis" in data["components"]
