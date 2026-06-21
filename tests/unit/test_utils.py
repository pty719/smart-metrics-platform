"""Unit tests for utility functions (Phase 0 smoke tests)."""
from __future__ import annotations

import pytest

from app.utils.math_utils import compute_percentile, sliding_window_averages
from app.utils.validators import validate_metric_name


class TestComputePercentile:
    """Tests for compute_percentile."""

    def test_median(self):
        assert compute_percentile([1, 2, 3, 4, 5], 50) == pytest.approx(3.0)

    def test_p90(self):
        result = compute_percentile([1, 2, 3, 4, 5], 90)
        assert result == pytest.approx(4.6)

    def test_single_element(self):
        assert compute_percentile([42.0], 50) == pytest.approx(42.0)

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="empty"):
            compute_percentile([], 50)

    def test_out_of_range_percentile(self):
        with pytest.raises(ValueError, match="percentile"):
            compute_percentile([1, 2, 3], 101)


class TestSlidingWindowAverages:
    """Tests for sliding_window_averages."""

    def test_window_3(self):
        result = sliding_window_averages([1, 2, 3, 4, 5], 3)
        assert result == pytest.approx([1.0, 1.5, 2.0, 3.0, 4.0])

    def test_window_1(self):
        values = [1.0, 2.0, 3.0]
        assert sliding_window_averages(values, 1) == pytest.approx(values)

    def test_window_larger_than_list(self):
        result = sliding_window_averages([1, 2], 10)
        assert result == pytest.approx([1.0, 1.5])

    def test_invalid_window(self):
        with pytest.raises(ValueError, match="window"):
            sliding_window_averages([1, 2, 3], 0)


class TestValidateMetricName:
    """Tests for validate_metric_name."""

    def test_valid_name(self):
        assert validate_metric_name("daily_users") == "daily_users"

    def test_starts_with_letter(self):
        with pytest.raises(ValueError):
            validate_metric_name("123bad")

    def test_special_chars(self):
        with pytest.raises(ValueError):
            validate_metric_name("has-dash")
