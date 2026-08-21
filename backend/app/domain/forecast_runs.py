"""Auditable stored forecast-run domain types."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

RunStatus = Literal["completed", "partial", "failed"]
SeriesRunStatus = Literal["succeeded", "failed"]
EvaluationStatus = Literal["succeeded", "failed"]


@dataclass(frozen=True, slots=True)
class ForecastRun:
    run_id: str
    data_version: str
    status: RunStatus
    created_at: datetime
    training_cutoff: date
    horizon_months: int
    interval_level: int
    series_count: int
    successful_series_count: int
    failed_series_count: int
    evaluation_count: int
    forecast_count: int


@dataclass(frozen=True, slots=True)
class ForecastSeriesResult:
    run_id: str
    store_id: str
    product_id: str
    sku: str
    product_name: str
    category: str
    status: SeriesRunStatus
    selected_model: str | None
    wape: float | None
    mase: float | None
    rmse: float | None
    bias: float | None
    interval_coverage: float | None
    validation_points: int | None
    failure_detail: str | None


@dataclass(frozen=True, slots=True)
class StoredModelEvaluation:
    run_id: str
    store_id: str
    product_id: str
    sku: str
    model_name: str
    selected: bool
    status: EvaluationStatus
    validation_origins: int
    wape: float | None
    mase: float | None
    rmse: float | None
    bias: float | None
    interval_coverage: float | None
    validation_points: int | None
    failure_detail: str | None


@dataclass(frozen=True, slots=True)
class StoredForecast:
    run_id: str
    store_id: str
    product_id: str
    sku: str
    period_start: date
    forecast_value: float
    lower_bound: float
    upper_bound: float
    horizon: int
    selected_model: str
    training_cutoff: date
