"""Unit tests for deterministic rolling-origin forecast selection."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

import pytest
from app.application.forecasting import (
    ForecastingEngine,
    InsufficientHistoryError,
    calculate_metrics,
)
from app.ports.forecasting import ForecastModel, ModelPrediction


@dataclass
class FakeModel:
    name: str
    complexity_rank: int
    predictor: Callable[[tuple[float, ...], int], tuple[float, ...]]
    fails: bool = False
    training_lengths: list[int] = field(default_factory=list)

    def predict(
        self, history: tuple[float, ...], horizon: int, interval_level: int
    ) -> ModelPrediction:
        del interval_level
        self.training_lengths.append(len(history))
        if self.fails:
            raise RuntimeError("deliberate candidate failure")
        mean = self.predictor(history, horizon)
        return ModelPrediction(
            mean=mean,
            lower=tuple(value - 1 for value in mean),
            upper=tuple(value + 1 for value in mean),
        )


def test_metrics_use_honest_denominators_and_interval_coverage() -> None:
    metrics = calculate_metrics(
        [10, 20],
        [12, 18],
        mase_denominators=[2, 2],
        lower=[9, 17],
        upper=[13, 21],
    )

    assert metrics.wape == pytest.approx(4 / 30)
    assert metrics.mase == pytest.approx(1)
    assert metrics.rmse == pytest.approx(2)
    assert metrics.bias == pytest.approx(0)
    assert metrics.interval_coverage == pytest.approx(1)
    assert metrics.validation_points == 2


def test_rolling_origin_selection_uses_expanding_training_and_isolates_failures() -> None:
    history = tuple(float(20 + month * 2 + month % 12) for month in range(60))
    oracle = FakeModel(
        "Oracle",
        2,
        lambda training, horizon: (
            history[len(training) : len(training) + horizon]
            if len(training) < len(history)
            else tuple(training[-1] + 2 * step for step in range(1, horizon + 1))
        ),
    )
    failing = FakeModel("Broken", 1, lambda _training, horizon: (0.0,) * horizon, fails=True)
    engine = ForecastingEngine(
        lambda *, intermittent: (failing, oracle) if not intermittent else (oracle,)
    )

    result = engine.run(history, training_cutoff=date(2026, 7, 1), horizon=6)

    assert result.selected_model == "Oracle"
    assert result.validation_origins == 4
    assert oracle.training_lengths == [36, 42, 48, 54, 60]
    assert result.selected_metrics.wape == pytest.approx(0)
    assert result.selected_metrics.mase == pytest.approx(0)
    assert result.selected_metrics.interval_coverage == pytest.approx(1)
    assert result.evaluations[0].status == "failed"
    assert result.evaluations[0].failure_detail is not None
    assert len(result.forecasts) == 6
    assert result.forecasts[0].period_start == date(2026, 8, 1)


def test_validation_rejects_random_split_sized_history_without_two_origins() -> None:
    model = FakeModel("Naive", 1, lambda training, horizon: (training[-1],) * horizon)
    engine = ForecastingEngine(lambda *, intermittent: (model,))

    with pytest.raises(InsufficientHistoryError, match="At least 48 completed months"):
        engine.run(range(47), training_cutoff=date(2026, 7, 1), horizon=6)


def test_all_zero_demand_has_an_explicit_zero_forecast() -> None:
    engine = ForecastingEngine(lambda *, intermittent: ())

    result = engine.run([0] * 48, training_cutoff=date(2026, 7, 1), horizon=3)

    assert result.selected_model == "Zero"
    assert result.selected_metrics.wape is None
    assert result.selected_metrics.mase is None
    assert all(point.forecast_value == 0 for point in result.forecasts)


def test_intermittent_history_uses_the_intermittent_candidate_registry() -> None:
    demand_types: list[bool] = []
    model = FakeModel("Sparse", 1, lambda training, horizon: (training[-1],) * horizon)

    def candidates(*, intermittent: bool) -> tuple[ForecastModel, ...]:
        demand_types.append(intermittent)
        return (model,)

    ForecastingEngine(candidates).run(
        [0, 0, 0, 5] * 12,
        training_cutoff=date(2026, 7, 1),
        horizon=6,
    )

    assert demand_types == [True]
