"""Unit tests for the ForecastEngine — model selection, gap-filling, intervals."""

from __future__ import annotations

from datetime import date

import pytest

from app.core.errors import InsufficientHistoryError
from app.models.enums import ForecastModel
from app.services.forecasting.engine import ForecastEngine, add_months, normalise_period
from app.services.forecasting.types import Observation

pytestmark = pytest.mark.unit


def obs(period: date, units: float) -> Observation:
    return Observation(period_start=period, units=units)


class TestDateHelpers:
    def test_add_months_rolls_over_year(self) -> None:
        assert add_months(date(2025, 11, 1), 3) == date(2026, 2, 1)

    def test_add_months_handles_negative(self) -> None:
        assert add_months(date(2025, 1, 1), -1) == date(2024, 12, 1)

    def test_normalise_period_snaps_to_first(self) -> None:
        assert normalise_period(date(2025, 6, 17)) == date(2025, 6, 1)


class TestForecastEngineReadmeExample:
    def test_reproduces_readme_worked_example(self) -> None:
        """Jan=100, Feb=120, Mar=140, Apr=160 -> May forecast of 180 units."""
        engine = ForecastEngine(min_history_periods=4, holdout_periods=1)
        history = [
            obs(date(2025, 1, 1), 100),
            obs(date(2025, 2, 1), 120),
            obs(date(2025, 3, 1), 140),
            obs(date(2025, 4, 1), 160),
        ]

        result = engine.forecast(history, horizon=1)

        assert result.points[0].period_start == date(2025, 5, 1)
        assert result.points[0].forecast_units == pytest.approx(180.0, abs=0.5)


class TestInsufficientHistory:
    def test_empty_history_raises(self) -> None:
        engine = ForecastEngine()
        with pytest.raises(InsufficientHistoryError):
            engine.forecast([], horizon=3)

    def test_below_minimum_periods_raises(self) -> None:
        engine = ForecastEngine(min_history_periods=6)
        history = [obs(date(2025, 1, 1), 10), obs(date(2025, 2, 1), 12)]
        with pytest.raises(InsufficientHistoryError) as excinfo:
            engine.forecast(history, horizon=1)
        assert excinfo.value.details["periods_available"] == 2

    def test_rejects_non_positive_horizon(self) -> None:
        engine = ForecastEngine(min_history_periods=1)
        with pytest.raises(ValueError):
            engine.forecast([obs(date(2025, 1, 1), 10)], horizon=0)


class TestGapFilling:
    def test_missing_month_is_filled_with_zero(self) -> None:
        """A skipped month must not silently compress the series."""
        engine = ForecastEngine(min_history_periods=3, holdout_periods=1)
        history = [
            obs(date(2025, 1, 1), 100),
            # February missing entirely
            obs(date(2025, 3, 1), 100),
            obs(date(2025, 4, 1), 100),
        ]
        result = engine.forecast(history, horizon=1)
        # 4 dense months (Jan..Apr) went into the model, not 3.
        assert result.history_periods == 4

    def test_duplicate_entries_in_same_period_are_summed(self) -> None:
        engine = ForecastEngine(min_history_periods=2, holdout_periods=0)
        history = [
            obs(date(2025, 1, 1), 50),
            obs(date(2025, 1, 1), 50),
            obs(date(2025, 2, 1), 100),
        ]
        result = engine.forecast(history, horizon=1)
        assert result.history_periods == 2


class TestModelSelection:
    def test_explicit_model_is_honoured(self) -> None:
        engine = ForecastEngine(min_history_periods=4, holdout_periods=1)
        history = [obs(date(2025, m, 1), 100 + m * 10) for m in range(1, 7)]
        result = engine.forecast(history, horizon=1, model=ForecastModel.NAIVE.value)
        assert result.model_used == ForecastModel.NAIVE.value

    def test_unknown_model_raises_value_error(self) -> None:
        engine = ForecastEngine(min_history_periods=1)
        with pytest.raises(ValueError):
            engine.forecast([obs(date(2025, 1, 1), 1)], horizon=1, model="not-a-real-model")

    def test_auto_selects_and_reports_scoreboard(self) -> None:
        engine = ForecastEngine(min_history_periods=4, holdout_periods=1)
        history = [obs(date(2025, m, 1), 100 + m * 15) for m in range(1, 8)]
        result = engine.forecast(history, horizon=2, model=ForecastModel.AUTO.value)
        assert result.model_used in result.candidates_evaluated
        assert len(result.candidates_evaluated) >= 2


class TestPredictionIntervals:
    def test_bounds_widen_with_horizon(self) -> None:
        engine = ForecastEngine(min_history_periods=4, holdout_periods=1)
        history = [
            obs(date(2025, 1, 1), 100),
            obs(date(2025, 2, 1), 105),
            obs(date(2025, 3, 1), 98),
            obs(date(2025, 4, 1), 110),
            obs(date(2025, 5, 1), 102),
        ]
        result = engine.forecast(history, horizon=4)
        widths = [p.upper_bound_units - p.lower_bound_units for p in result.points]
        assert widths == sorted(widths)  # non-decreasing

    def test_lower_bound_never_negative(self) -> None:
        engine = ForecastEngine(min_history_periods=3, holdout_periods=0)
        history = [obs(date(2025, m, 1), 1) for m in range(1, 5)]
        result = engine.forecast(history, horizon=3)
        assert all(p.lower_bound_units >= 0 for p in result.points)

    def test_confidence_level_is_recorded(self) -> None:
        engine = ForecastEngine(min_history_periods=3, holdout_periods=0, confidence_level=0.90)
        history = [obs(date(2025, m, 1), 10 + m) for m in range(1, 5)]
        result = engine.forecast(history, horizon=1)
        assert result.confidence_level == 0.90


class TestGracefulDegradation:
    def test_short_series_still_forecasts_with_naive_style_model(self) -> None:
        engine = ForecastEngine(min_history_periods=2, holdout_periods=3)
        history = [obs(date(2025, 1, 1), 40), obs(date(2025, 2, 1), 44)]
        result = engine.forecast(history, horizon=1)
        assert result.points[0].forecast_units > 0
