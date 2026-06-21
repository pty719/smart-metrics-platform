"""Unit tests for stats_service.

Uses the real in-memory SQLite test database (via ``db_session`` fixture)
and mocks Redis to isolate cache behaviour.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidDataError, MetricNotFoundError
from app.models.datapoint import Datapoint
from app.models.metric import Metric
from app.services import datapoint_service, metric_service, stats_service


# ── Helpers ────────────────────────────────────────────────────────────


async def _seed_metric_with_values(
    db: AsyncSession, name: str, values: list[float]
) -> None:
    """Create a metric and attach datapoints for it."""
    metric = await metric_service.create_metric(db, name=name)
    await datapoint_service.create_datapoints(
        db,
        metric_name=name,
        datapoints=[{"value": v} for v in values],
    )


def _mock_redis() -> AsyncMock:
    """Return a mock Redis client that always cache-misses."""
    mock = AsyncMock()
    mock.get.return_value = None  # always miss
    mock.set.return_value = True
    return mock


# ── get_stats ─────────────────────────────────────────────────────────


class TestGetStats:
    """stats_service.get_stats"""

    @pytest.mark.asyncio
    async def test_returns_correct_stats(self, db_session: AsyncSession) -> None:
        """Should return mean, min, max, std_dev, median."""
        await _seed_metric_with_values(db_session, "s1", [1.0, 2.0, 3.0, 4.0, 5.0])

        mock_redis = _mock_redis()
        with patch("app.services.stats_service.get_redis", return_value=mock_redis):
            result = await stats_service.get_stats(db_session, metric_name="s1")

        assert result["metric_name"] == "s1"
        assert result["count"] == 5
        assert abs(result["mean"] - 3.0) < 1e-6
        assert result["min"] == 1.0
        assert result["max"] == 5.0
        assert result["median"] == 3.0
        assert result["std_dev"] is not None  # n >= 2

    @pytest.mark.asyncio
    async def test_single_value_no_std_dev(self, db_session: AsyncSession) -> None:
        """When only one datapoint exists, std_dev should be None."""
        await _seed_metric_with_values(db_session, "s_single", [42.0])

        mock_redis = _mock_redis()
        with patch("app.services.stats_service.get_redis", return_value=mock_redis):
            result = await stats_service.get_stats(db_session, metric_name="s_single")

        assert result["count"] == 1
        assert result["std_dev"] is None

    @pytest.mark.asyncio
    async def test_nonexistent_metric_raises(self, db_session: AsyncSession) -> None:
        """Should raise MetricNotFoundError."""
        mock_redis = _mock_redis()
        with patch("app.services.stats_service.get_redis", return_value=mock_redis):
            with pytest.raises(MetricNotFoundError):
                await stats_service.get_stats(db_session, metric_name="no_such")

    @pytest.mark.asyncio
    async def test_no_datapoints_raises(self, db_session: AsyncSession) -> None:
        """Should raise InvalidDataError when metric has no data."""
        await metric_service.create_metric(db_session, name="s_empty")
        mock_redis = _mock_redis()
        with patch("app.services.stats_service.get_redis", return_value=mock_redis):
            with pytest.raises(InvalidDataError):
                await stats_service.get_stats(db_session, metric_name="s_empty")

    @pytest.mark.asyncio
    async def test_uses_cache(self, db_session: AsyncSession) -> None:
        """When Redis has a cached value, it should be returned directly."""
        cached = {"metric_name": "s_cached", "count": 1, "mean": 1.0}
        mock_redis = _mock_redis()
        mock_redis.get.return_value = __import__("json").dumps(cached)

        with patch("app.services.stats_service.get_redis", return_value=mock_redis):
            result = await stats_service.get_stats(db_session, metric_name="s_cached")

        assert result["metric_name"] == "s_cached"
        mock_redis.get.assert_awaited_once()
        mock_redis.set.assert_not_called()


# ── get_anomalies ────────────────────────────────────────────────────


class TestGetAnomalies:
    """stats_service.get_anomalies"""

    @pytest.mark.asyncio
    async def test_detects_outliers(self, db_session: AsyncSession) -> None:
        """Values far from the mean should be flagged as anomalies."""
        # mean=5, std~2.236, 3σ ~ 6.7 → [−1.7, 11.7]
        # 100 is an anomaly
        vals = [3.0, 4.0, 5.0, 6.0, 7.0, 100.0]
        await _seed_metric_with_values(db_session, "a1", vals)

        mock_redis = _mock_redis()
        with patch("app.services.stats_service.get_redis", return_value=mock_redis):
            result = await stats_service.get_anomalies(db_session, metric_name="a1")

        assert result["anomaly_count"] == 1
        assert len(result["anomalies"]) == 1
        assert result["anomalies"][0]["value"] == 100.0

    @pytest.mark.asyncio
    async def test_no_anomalies(self, db_session: AsyncSession) -> None:
        """When all values are within 3σ, anomaly_count should be 0."""
        vals = [10.0, 11.0, 12.0, 13.0, 14.0]
        await _seed_metric_with_values(db_session, "a_none", vals)

        mock_redis = _mock_redis()
        with patch("app.services.stats_service.get_redis", return_value=mock_redis):
            result = await stats_service.get_anomalies(
                db_session, metric_name="a_none"
            )

        assert result["anomaly_count"] == 0
        assert result["anomalies"] == []

    @pytest.mark.asyncio
    async def test_nonexistent_metric_raises(self, db_session: AsyncSession) -> None:
        mock_redis = _mock_redis()
        with patch("app.services.stats_service.get_redis", return_value=mock_redis):
            with pytest.raises(MetricNotFoundError):
                await stats_service.get_anomalies(db_session, metric_name="no_such")


# ── get_moving_average ────────────────────────────────────────────────


class TestGetMovingAverage:
    """stats_service.get_moving_average"""

    @pytest.mark.asyncio
    async def test_returns_correct_ma(self, db_session: AsyncSession) -> None:
        """Verify moving average values for a simple series."""
        # values: [10, 20, 30, 40]
        # window=2 MA: [10/1=10, (10+20)/2=15, (20+30)/2=25, (30+40)/2=35]
        await _seed_metric_with_values(db_session, "ma1", [10.0, 20.0, 30.0, 40.0])

        mock_redis = _mock_redis()
        with patch("app.services.stats_service.get_redis", return_value=mock_redis):
            result = await stats_service.get_moving_average(
                db_session, metric_name="ma1", window=2
            )

        assert result["window"] == 2
        assert len(result["data_points"]) == 4
        pts = result["data_points"]
        assert abs(pts[0]["moving_average"] - 10.0) < 1e-6
        assert abs(pts[1]["moving_average"] - 15.0) < 1e-6
        assert abs(pts[2]["moving_average"] - 25.0) < 1e-6
        assert abs(pts[3]["moving_average"] - 35.0) < 1e-6

    @pytest.mark.asyncio
    async def test_window_1_equals_raw_values(self, db_session: AsyncSession) -> None:
        """Window size 1 should return the raw values as the moving average."""
        await _seed_metric_with_values(db_session, "ma_w1", [1.0, 2.0, 3.0])

        mock_redis = _mock_redis()
        with patch("app.services.stats_service.get_redis", return_value=mock_redis):
            result = await stats_service.get_moving_average(
                db_session, metric_name="ma_w1", window=1
            )

        for pt in result["data_points"]:
            assert abs(pt["moving_average"] - pt["value"]) < 1e-6

    @pytest.mark.asyncio
    async def test_invalid_window_raises(self, db_session: AsyncSession) -> None:
        """Window < 1 should raise InvalidDataError."""
        await _seed_metric_with_values(db_session, "ma_bad", [1.0])

        mock_redis = _mock_redis()
        with patch("app.services.stats_service.get_redis", return_value=mock_redis):
            with pytest.raises(InvalidDataError):
                await stats_service.get_moving_average(
                    db_session, metric_name="ma_bad", window=0
                )

    @pytest.mark.asyncio
    async def test_nonexistent_metric_raises(self, db_session: AsyncSession) -> None:
        mock_redis = _mock_redis()
        with patch("app.services.stats_service.get_redis", return_value=mock_redis):
            with pytest.raises(MetricNotFoundError):
                await stats_service.get_moving_average(
                    db_session, metric_name="no_such"
                )
