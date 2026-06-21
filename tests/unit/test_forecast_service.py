"""Unit tests for forecast_service linear regression algorithm.

These tests target the **pure functions** only (``linear_forecast``,
``build_forecast_result``) and do NOT require a database or Celery.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from app.core.exceptions import InvalidDataError
from app.services.forecast_service import build_forecast_result, linear_forecast


class TestLinearForecast:
    """Tests for the pure ``linear_forecast`` function."""

    def test_perfect_linear_relationship(self) -> None:
        """When y = 2*x + 3 exactly, slope=2 and intercept=3."""
        x = [0.0, 1.0, 2.0, 3.0, 4.0]
        y = [3.0, 5.0, 7.0, 9.0, 11.0]  # y = 2x + 3

        result = linear_forecast(x, y, steps=2)

        assert math.isclose(result["slope"], 2.0, rel_tol=1e-6)
        assert math.isclose(result["intercept"], 3.0, rel_tol=1e-6)
        assert math.isclose(result["r_squared"], 1.0, rel_tol=1e-6)

    def test_forecast_extrapolates_correctly(self) -> None:
        """Forecast values should lie on the fitted line."""
        x = [0.0, 1.0, 2.0]
        y = [1.0, 3.0, 5.0]  # slope=2, intercept=1

        result = linear_forecast(x, y, steps=2)

        # Next x values: 3.0, 4.0 → predicted y: 7.0, 9.0
        assert math.isclose(result["forecast_y"][0], 7.0, rel_tol=1e-6)
        assert math.isclose(result["forecast_y"][1], 9.0, rel_tol=1e-6)

    def test_confidence_interval_contains_prediction(self) -> None:
        """Lower bound < prediction < upper bound for each forecast point."""
        x = list(range(10))
        y = [float(i) + 0.1 for i in x]  # roughly y = x

        result = linear_forecast(x, y, steps=3, conf_level=0.95)

        for i in range(3):
            assert result["lower_bound"][i] < result["forecast_y"][i]
            assert result["forecast_y"][i] < result["upper_bound"][i]

    def test_insufficient_data_raises(self) -> None:
        """Fewer than 2 points must raise InvalidDataError."""
        with pytest.raises(InvalidDataError):
            linear_forecast([1.0], [2.0], steps=1)

    def test_mismatched_lengths_raise(self) -> None:
        """x and y of different lengths must raise InvalidDataError."""
        with pytest.raises(InvalidDataError):
            linear_forecast([1.0, 2.0], [1.0], steps=1)

    def test_r_squared_low_for_noisy_data(self) -> None:
        """Noisy data should have low R²."""
        x = [0.0, 1.0, 2.0, 3.0, 4.0]
        y = [0.0, 100.0, 0.0, 100.0, 0.0]  # no linear pattern

        result = linear_forecast(x, y, steps=1)
        assert result["r_squared"] < 0.5


class TestBuildForecastResult:
    """Tests for ``build_forecast_result`` (still pure — uses fake datapoints)."""

    def _make_datapoints(self, values: list[float]) -> list:
        """Create lightweight fake datapoint objects."""

        class FakeDatapoint:
            def __init__(self, value: float, idx: int) -> None:
                self.value = value
                self.timestamp = datetime(2026, 1, 1, idx, 0, 0, tzinfo=timezone.utc)
                self.id = idx

        return [FakeDatapoint(v, i) for i, v in enumerate(values)]

    def test_build_result_structure(self) -> None:
        """Result should contain ``history`` and ``forecast`` keys."""
        dps = self._make_datapoints([10.0, 20.0, 30.0])

        result = build_forecast_result("test_metric", dps, steps=2)

        assert result["metric_name"] == "test_metric"
        assert result["model"] == "linear_regression"
        assert len(result["history"]) == 3
        assert len(result["forecast"]) == 2

    def test_forecast_timestamps_are_isoformat(self) -> None:
        """Forecast timestamps should be ISO-formatted strings."""
        dps = self._make_datapoints([10.0, 20.0, 30.0])

        result = build_forecast_result("m", dps, steps=1)

        # Should parse without error
        datetime.fromisoformat(result["forecast"][0]["timestamp"])

    def test_insufficient_datapoints_raises(self) -> None:
        """Fewer than 2 datapoints should raise InvalidDataError."""
        dps = self._make_datapoints([1.0])

        with pytest.raises(InvalidDataError):
            build_forecast_result("m", dps, steps=1)
