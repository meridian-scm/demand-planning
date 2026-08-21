"""StatsForecast adapters behind Meridian's model port."""

from collections.abc import Callable
from typing import Protocol, cast

import numpy as np
from numpy.typing import NDArray
from statsforecast.models import (
    AutoETS,
    AutoTheta,
    CrostonOptimized,
    Naive,
    RandomWalkWithDrift,
    SeasonalNaive,
)

from app.ports.forecasting import ForecastModel, ModelPrediction


class _StatsForecastModel(Protocol):
    def forecast(
        self,
        y: NDArray[np.float64],
        h: int,
        *,
        level: list[int] | None = None,
    ) -> dict[str, NDArray[np.float64]]: ...


class StatsForecastModelAdapter:
    """Create a fresh StatsForecast model for every isolated fit."""

    def __init__(
        self,
        name: str,
        complexity_rank: int,
        factory: Callable[[], object],
        *,
        native_intervals: bool = True,
    ) -> None:
        self._name = name
        self._complexity_rank = complexity_rank
        self._factory = factory
        self._native_intervals = native_intervals

    @property
    def name(self) -> str:
        return self._name

    @property
    def complexity_rank(self) -> int:
        return self._complexity_rank

    def predict(
        self, history: tuple[float, ...], horizon: int, interval_level: int
    ) -> ModelPrediction:
        model = cast(_StatsForecastModel, self._factory())
        output = model.forecast(
            np.asarray(history, dtype=np.float64),
            horizon,
            level=[interval_level] if self._native_intervals else None,
        )
        mean = tuple(float(value) for value in output["mean"])
        if not self._native_intervals:
            return ModelPrediction(mean=mean)
        return ModelPrediction(
            mean=mean,
            lower=tuple(float(value) for value in output[f"lo-{interval_level}"]),
            upper=tuple(float(value) for value in output[f"hi-{interval_level}"]),
        )


def build_candidate_models(*, intermittent: bool) -> tuple[ForecastModel, ...]:
    """Return the controlled candidate set eligible for a monthly demand type."""

    naive = StatsForecastModelAdapter("Naive", 1, Naive)
    seasonal_naive = StatsForecastModelAdapter(
        "SeasonalNaive", 2, lambda: SeasonalNaive(season_length=12)
    )
    if intermittent:
        return (
            naive,
            seasonal_naive,
            StatsForecastModelAdapter(
                "CrostonOptimized", 3, CrostonOptimized, native_intervals=False
            ),
        )
    return (
        naive,
        seasonal_naive,
        StatsForecastModelAdapter("RandomWalkWithDrift", 3, RandomWalkWithDrift),
        StatsForecastModelAdapter("AutoETS", 4, lambda: AutoETS(season_length=12)),
        StatsForecastModelAdapter("AutoTheta", 5, lambda: AutoTheta(season_length=12)),
    )
