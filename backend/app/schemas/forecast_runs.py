"""HTTP schemas for immutable forecast-run retrieval."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ForecastRunResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    data_version: str
    status: Literal["completed", "partial", "failed"]
    created_at: datetime
    training_cutoff: date
    horizon_months: int
    interval_level: int
    series_count: int
    successful_series_count: int
    failed_series_count: int
    evaluation_count: int
    forecast_count: int


class ForecastSeriesResultResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    store_id: str
    product_id: str
    sku: str
    product_name: str
    category: str
    status: Literal["succeeded", "failed"]
    selected_model: str | None
    wape: float | None
    mase: float | None
    rmse: float | None
    bias: float | None
    interval_coverage: float | None
    validation_points: int | None
    failure_detail: str | None


class StoredModelEvaluationResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    store_id: str
    product_id: str
    sku: str
    model_name: str
    selected: bool
    status: Literal["succeeded", "failed"]
    validation_origins: int
    wape: float | None
    mase: float | None
    rmse: float | None
    bias: float | None
    interval_coverage: float | None
    validation_points: int | None
    failure_detail: str | None


class StoredForecastResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

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
