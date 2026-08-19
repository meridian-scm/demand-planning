"""Value objects passed through the forecasting pipeline.

These are deliberately plain dataclasses rather than ORM or Pydantic objects:
the engine is pure and can be unit-tested without a database or a web request.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True, slots=True)
class Observation:
    """One historical period of demand."""

    period_start: date
    units: float


@dataclass(frozen=True, slots=True)
class ForecastPoint:
    """One predicted future period, with an uncertainty band."""

    period_start: date
    forecast_units: float
    lower_bound_units: float
    upper_bound_units: float


@dataclass(frozen=True, slots=True)
class AccuracyMetrics:
    """Backtest error measures for a fitted model.

    ``wape`` (weighted absolute percentage error) is the primary selection
    metric because MAPE explodes when a period has zero demand, which happens
    routinely for slow-moving SKUs.
    """

    mape: float | None
    wape: float | None
    rmse: float | None
    bias: float | None = None

    @property
    def is_scored(self) -> bool:
        return self.wape is not None


@dataclass(slots=True)
class ForecastResult:
    """The engine's output for a single product."""

    model_used: str
    points: list[ForecastPoint]
    metrics: AccuracyMetrics
    params: dict = field(default_factory=dict)
    confidence_level: float = 0.95
    history_periods: int = 0
    candidates_evaluated: dict[str, float | None] = field(default_factory=dict)

    @property
    def total_forecast_units(self) -> float:
        return sum(point.forecast_units for point in self.points)
