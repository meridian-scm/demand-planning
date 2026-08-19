"""Unit tests for forecast accuracy metrics."""

from __future__ import annotations

import pytest

from app.services.forecasting.metrics import bias, evaluate, mape, rmse, wape

pytestmark = pytest.mark.unit


class TestMape:
    def test_perfect_forecast_is_zero(self) -> None:
        assert mape([10, 20, 30], [10, 20, 30]) == pytest.approx(0.0)

    def test_known_value(self) -> None:
        # |10-8|/10 = 0.2, |20-25|/20 = 0.25 -> mean 0.225 -> 22.5%
        assert mape([10, 20], [8, 25]) == pytest.approx(22.5)

    def test_ignores_zero_actuals(self) -> None:
        assert mape([0, 10], [5, 10]) == pytest.approx(0.0)

    def test_all_zero_actuals_returns_none(self) -> None:
        assert mape([0, 0], [1, 2]) is None

    def test_length_mismatch_raises(self) -> None:
        with pytest.raises(ValueError):
            mape([1, 2, 3], [1, 2])


class TestWape:
    def test_perfect_forecast_is_zero(self) -> None:
        assert wape([10, 20, 30], [10, 20, 30]) == pytest.approx(0.0)

    def test_known_value(self) -> None:
        # sum|error| = 2+5 = 7, sum|actual| = 30 -> 23.33%
        assert wape([10, 20], [8, 25]) == pytest.approx(7 / 30 * 100)

    def test_handles_zero_actual_periods_via_denominator(self) -> None:
        # denominator uses the sum, not each period, so a single zero period
        # does not blow up the metric the way MAPE would.
        result = wape([0, 10], [5, 10])
        assert result == pytest.approx(5 / 10 * 100)

    def test_all_zero_actuals_returns_none(self) -> None:
        assert wape([0, 0], [1, 2]) is None


class TestRmse:
    def test_known_value(self) -> None:
        # errors: 2, 5 -> squared: 4, 25 -> mean 14.5 -> sqrt ~3.808
        assert rmse([10, 20], [8, 25]) == pytest.approx(14.5**0.5)

    def test_empty_series_returns_none(self) -> None:
        assert rmse([], []) is None


class TestBias:
    def test_over_forecast_is_positive(self) -> None:
        result = bias([10, 10], [12, 12])
        assert result is not None and result > 0

    def test_under_forecast_is_negative(self) -> None:
        result = bias([10, 10], [8, 8])
        assert result is not None and result < 0

    def test_perfect_forecast_is_zero(self) -> None:
        assert bias([10, 20], [10, 20]) == pytest.approx(0.0)


class TestEvaluate:
    def test_returns_all_metrics(self) -> None:
        result = evaluate([10, 20, 30], [11, 19, 31])
        assert result.mape is not None
        assert result.wape is not None
        assert result.rmse is not None
        assert result.bias is not None
        assert result.is_scored

    def test_degenerate_series_is_unscored_but_does_not_raise(self) -> None:
        result = evaluate([0, 0], [1, 2])
        assert result.wape is None
        assert result.mape is None
        assert not result.is_scored
