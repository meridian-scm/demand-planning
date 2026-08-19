"""Unit tests for individual forecasting algorithms."""

from __future__ import annotations

import numpy as np
import pytest

from app.services.forecasting.algorithms import (
    AlgorithmNotApplicable,
    holt_linear,
    holt_winters,
    linear_trend,
    moving_average,
    naive,
    seasonal_naive,
)

pytestmark = pytest.mark.unit


class TestNaive:
    def test_forecasts_flat_at_last_value(self) -> None:
        result = naive([10, 20, 15, 30], horizon=3)
        assert result.forecast.tolist() == [30.0, 30.0, 30.0]

    def test_fitted_values_are_lagged_by_one(self) -> None:
        result = naive([10, 20, 15], horizon=1)
        assert result.fitted.tolist() == [10.0, 10.0, 20.0]

    def test_rejects_empty_series(self) -> None:
        with pytest.raises(AlgorithmNotApplicable):
            naive([], horizon=1)


class TestMovingAverage:
    def test_uses_trailing_window_mean(self) -> None:
        result = moving_average([10, 20, 30, 40], horizon=1, window=2)
        assert result.forecast[0] == pytest.approx(35.0)

    def test_window_larger_than_series_uses_full_series(self) -> None:
        result = moving_average([10, 20], horizon=1, window=10)
        assert result.forecast[0] == pytest.approx(15.0)

    def test_never_negative(self) -> None:
        result = moving_average([0, 0, 0], horizon=2, window=3)
        assert all(value >= 0 for value in result.forecast)


class TestSeasonalNaive:
    def test_repeats_last_season(self) -> None:
        series = list(range(1, 13))  # 1..12, one full season
        result = seasonal_naive(series, horizon=3, seasonal_periods=12)
        assert result.forecast.tolist() == [1.0, 2.0, 3.0]

    def test_requires_full_season(self) -> None:
        with pytest.raises(AlgorithmNotApplicable):
            seasonal_naive([1, 2, 3], horizon=1, seasonal_periods=12)


class TestLinearTrend:
    def test_reproduces_readme_example(self) -> None:
        """100, 120, 140, 160 -> May forecast of 180, per the project brief."""
        result = linear_trend([100, 120, 140, 160], horizon=1)
        assert result.forecast[0] == pytest.approx(180.0, abs=1e-6)

    def test_flat_series_has_zero_slope(self) -> None:
        result = linear_trend([50, 50, 50, 50], horizon=2)
        assert result.forecast.tolist() == pytest.approx([50.0, 50.0])
        assert result.params["slope"] == pytest.approx(0.0, abs=1e-9)

    def test_requires_two_points(self) -> None:
        with pytest.raises(AlgorithmNotApplicable):
            linear_trend([42], horizon=1)

    def test_clips_negative_forecast_to_zero(self) -> None:
        result = linear_trend([100, 50, 0], horizon=2)
        assert all(value >= 0 for value in result.forecast)


class TestHoltLinear:
    def test_extrapolates_upward_trend(self) -> None:
        series = [10, 20, 30, 40, 50, 60]
        result = holt_linear(series, horizon=2)
        assert result.forecast[0] > series[-1]
        assert result.forecast[1] > result.forecast[0]

    def test_requires_three_points(self) -> None:
        with pytest.raises(AlgorithmNotApplicable):
            holt_linear([1, 2], horizon=1)

    def test_params_include_selected_smoothing_constants(self) -> None:
        result = holt_linear([10, 12, 14, 16, 18], horizon=1)
        assert 0 < result.params["alpha"] <= 0.9
        assert 0 < result.params["beta"] <= 0.5


class TestHoltWinters:
    def test_requires_two_full_seasons(self) -> None:
        with pytest.raises(AlgorithmNotApplicable):
            holt_winters(list(range(12)), horizon=1, seasonal_periods=12)

    def test_captures_seasonal_pattern(self) -> None:
        # Two identical seasonal cycles with a mild upward trend.
        base = [10, 12, 30, 15, 10, 8, 9, 11, 14, 20, 16, 12]
        series = base + [v + 2 for v in base]
        result = holt_winters(series, horizon=12, seasonal_periods=12)
        # The peak month (index 2, value 30-ish) should still forecast as the
        # local maximum within the projected season.
        assert int(np.argmax(result.forecast)) == 2

    def test_rejects_seasonal_periods_below_two(self) -> None:
        with pytest.raises(AlgorithmNotApplicable):
            holt_winters([1, 2, 3, 4], horizon=1, seasonal_periods=1)
