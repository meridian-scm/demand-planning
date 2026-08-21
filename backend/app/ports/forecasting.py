"""Forecast-model port used by the deterministic selection engine."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ModelPrediction:
    """Storage-neutral numerical output from one candidate model."""

    mean: tuple[float, ...]
    lower: tuple[float, ...] | None = None
    upper: tuple[float, ...] | None = None


class ForecastModel(Protocol):
    """Minimal candidate-model contract."""

    @property
    def name(self) -> str: ...

    @property
    def complexity_rank(self) -> int: ...

    def predict(
        self, history: tuple[float, ...], horizon: int, interval_level: int
    ) -> ModelPrediction:
        """Fit to history and forecast the next horizon."""
