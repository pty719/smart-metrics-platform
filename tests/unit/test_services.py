"""Unit tests for metric_service and datapoint_service.

Instead of mocking every SQLAlchemy call (which is brittle and complex),
these tests use the real in-memory SQLite test database provided by
the ``db_session`` fixture from ``conftest.py``.
"""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from decimal import Decimal

from app.core.exceptions import DuplicateMetricError, InvalidDataError, MetricNotFoundError
from app.models.datapoint import Datapoint
from app.models.metric import Metric
from app.services import datapoint_service, metric_service


# ── metric_service tests ──────────────────────────────────────────

class TestCreateMetric:
    """metric_service.create_metric"""

    @pytest.mark.asyncio
    async def test_creates_and_returns_metric(self, db_session: AsyncSession) -> None:
        """Should persist a new metric and return it with an id."""
        metric = await metric_service.create_metric(
            db_session, name="new_metric", unit="人", description="测试"
        )
        assert metric.id is not None
        assert metric.name == "new_metric"
        assert metric.unit == "人"

    @pytest.mark.asyncio
    async def test_duplicate_name_raises(self, db_session: AsyncSession) -> None:
        """Should raise DuplicateMetricError when name already exists."""
        await metric_service.create_metric(db_session, name="dup")
        with pytest.raises(DuplicateMetricError):
            await metric_service.create_metric(db_session, name="dup")


class TestGetMetrics:
    """metric_service.get_metrics"""

    @pytest.mark.asyncio
    async def test_returns_items_and_total(self, db_session: AsyncSession) -> None:
        """Should return a (items, total) tuple."""
        for i in range(3):
            await metric_service.create_metric(db_session, name=f"m{i}")
        items, total = await metric_service.get_metrics(db_session, skip=0, limit=10)
        assert total == 3
        assert len(items) == 3

    @pytest.mark.asyncio
    async def test_pagination(self, db_session: AsyncSession) -> None:
        """skip and limit should control the result window."""
        for i in range(5):
            await metric_service.create_metric(db_session, name=f"p{i}")
        items, total = await metric_service.get_metrics(db_session, skip=2, limit=2)
        assert total == 5
        assert len(items) == 2


class TestGetMetricByName:
    """metric_service.get_metric_by_name"""

    @pytest.mark.asyncio
    async def test_existing_metric(self, db_session: AsyncSession) -> None:
        """Should return the metric when it exists."""
        await metric_service.create_metric(db_session, name="find_me")
        metric = await metric_service.get_metric_by_name(db_session, name="find_me")
        assert metric.name == "find_me"

    @pytest.mark.asyncio
    async def test_nonexistent_raises(self, db_session: AsyncSession) -> None:
        """Should raise MetricNotFoundError."""
        with pytest.raises(MetricNotFoundError):
            await metric_service.get_metric_by_name(db_session, name="nope")


class TestDeleteMetric:
    """metric_service.delete_metric"""

    @pytest.mark.asyncio
    async def test_deletes_existing(self, db_session: AsyncSession) -> None:
        """Should delete the metric; subsequent fetch raises."""
        await metric_service.create_metric(db_session, name="to_delete")
        await metric_service.delete_metric(db_session, name="to_delete")
        await db_session.flush()
        # After flush, the metric is gone from the DB;
        # a fresh lookup must raise.
        with pytest.raises(MetricNotFoundError):
            await metric_service.get_metric_by_name(db_session, name="to_delete")


# ── datapoint_service tests ──────────────────────────────────────

class TestCreateDatapoints:
    """datapoint_service.create_datapoints"""

    @pytest.mark.asyncio
    async def test_creates_single_datapoint(self, db_session: AsyncSession) -> None:
        """Should persist one datapoint and return it."""
        await metric_service.create_metric(db_session, name="dp_test")
        records = await datapoint_service.create_datapoints(
            db_session, metric_name="dp_test", datapoints=[{"value": 3.14}]
        )
        assert len(records) == 1
        assert records[0].value == Decimal("3.140000")

    @pytest.mark.asyncio
    async def test_creates_multiple(self, db_session: AsyncSession) -> None:
        """Should persist multiple datapoints."""
        await metric_service.create_metric(db_session, name="dp_multi")
        records = await datapoint_service.create_datapoints(
            db_session,
            metric_name="dp_multi",
            datapoints=[{"value": 1.0}, {"value": 2.0}],
        )
        assert len(records) == 2

    @pytest.mark.asyncio
    async def test_infinite_value_raises(self, db_session: AsyncSession) -> None:
        """Should raise InvalidDataError for inf values."""
        import math

        await metric_service.create_metric(db_session, name="dp_bad")
        with pytest.raises(InvalidDataError):
            await datapoint_service.create_datapoints(
                db_session,
                metric_name="dp_bad",
                datapoints=[{"value": math.inf}],
            )

    @pytest.mark.asyncio
    async def test_nonexistent_metric_raises(self, db_session: AsyncSession) -> None:
        """Should raise MetricNotFoundError for bad metric name."""
        with pytest.raises(MetricNotFoundError):
            await datapoint_service.create_datapoints(
                db_session, metric_name="no_such", datapoints=[{"value": 1.0}]
            )


class TestGetDatapoints:
    """datapoint_service.get_datapoints"""

    @pytest.mark.asyncio
    async def test_returns_all(self, db_session: AsyncSession) -> None:
        """Should return all datapoints for a metric."""
        await metric_service.create_metric(db_session, name="q_test")
        await datapoint_service.create_datapoints(
            db_session,
            metric_name="q_test",
            datapoints=[{"value": 1.0}, {"value": 2.0}],
        )
        items, total = await datapoint_service.get_datapoints(
            db_session, metric_name="q_test"
        )
        assert total == 2
        assert len(items) == 2

    @pytest.mark.asyncio
    async def test_nonexistent_metric_raises(self, db_session: AsyncSession) -> None:
        """Should raise MetricNotFoundError."""
        with pytest.raises(MetricNotFoundError):
            await datapoint_service.get_datapoints(
                db_session, metric_name="no_such"
            )


class TestGetLatestValue:
    """datapoint_service.get_latest_value"""

    @pytest.mark.asyncio
    async def test_returns_latest(self, db_session: AsyncSession) -> None:
        """Should return the datapoint with the highest timestamp."""
        await metric_service.create_metric(db_session, name="latest_test")
        await datapoint_service.create_datapoints(
            db_session,
            metric_name="latest_test",
            datapoints=[{"value": 10.0}, {"value": 99.0}],
        )
        dp = await datapoint_service.get_latest_value(
            db_session, metric_name="latest_test"
        )
        assert dp.value == 99.0

    @pytest.mark.asyncio
    async def test_no_datapoints_raises(self, db_session: AsyncSession) -> None:
        """Should raise InvalidDataError when metric has no data."""
        await metric_service.create_metric(db_session, name="empty")
        with pytest.raises(InvalidDataError):
            await datapoint_service.get_latest_value(
                db_session, metric_name="empty"
            )
