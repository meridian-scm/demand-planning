"""Storage- and framework-independent forecasting result types."""

from dataclasses import dataclass
from datetime import date
from typing import Literal


@dataclass(frozen=True, slots=True)
class ForecastMetrics:
    """Validation metrics with undefined denominators represented honestly as null."""

    wape: float | None
    mase: float | None
    rmse: float
    bias: float | None
    interval_coverage: float | None
    validation_points: int


@dataclass(frozen=True, slots=True)
class ModelEvaluation:
    """Auditable outcome for one eligible candidate model."""

    model_name: str
    status: Literal["succeeded", "failed"]
    validation_origins: int
    metrics: ForecastMetrics | None
    failure_detail: str | None = None


@dataclass(frozen=True, slots=True)
class ForecastPoint:
    """One monthly point forecast and prediction interval."""

    period_start: date
    forecast_value: float
    lower_bound: float
    upper_bound: float
    horizon: int


@dataclass(frozen=True, slots=True)
class ForecastResult:
    """Selected forecast plus all candidate-validation evidence."""

    forecast_id: str
    selected_model: str
    training_cutoff: date
    horizon_months: int
    interval_level: int
    intermittent_demand: bool
    validation_origins: int
    selected_metrics: ForecastMetrics
    evaluations: tuple[ModelEvaluation, ...]
    forecasts: tuple[ForecastPoint, ...]
