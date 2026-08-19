"""Forecast request and response schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import ForecastModel
from app.schemas.common import ORMModel


class ForecastRunCreate(BaseModel):
    """Request to run a forecasting cycle."""

    horizon: int = Field(default=6, ge=1, le=36, description="Number of future months to project")
    model: ForecastModel = Field(
        default=ForecastModel.AUTO,
        description="Algorithm to use, or 'auto' to let the engine backtest and choose",
    )
    product_ids: list[int] | None = Field(
        default=None, description="Restrict the run to these products; omit for all active products"
    )
    run_label: str | None = Field(default=None, max_length=128)
    detect_exceptions: bool = Field(
        default=True, description="Refresh planning exceptions as part of the run"
    )


class ForecastRead(ORMModel):
    id: int
    run_id: int
    product_id: int
    period_start: date
    forecast_units: float
    lower_bound_units: float | None
    upper_bound_units: float | None
    model_used: str
    mape: float | None
    wape: float | None
    rmse: float | None
    confidence_level: float
    model_params: dict | None


class ForecastRunRead(ORMModel):
    id: int
    run_label: str
    requested_model: str
    horizon_periods: int
    products_forecasted: int
    products_skipped: int
    started_at: datetime
    completed_at: datetime | None
    notes: dict | None


class ForecastPointRead(BaseModel):
    period_start: date
    forecast_units: float
    lower_bound_units: float
    upper_bound_units: float


class ForecastPreview(BaseModel):
    """An unsaved forecast, used by the what-if view."""

    product_id: int
    sku: str
    name: str
    model_used: str
    history_periods: int
    confidence_level: float
    mape: float | None
    wape: float | None
    rmse: float | None
    candidates_evaluated: dict[str, float | None]
    points: list[ForecastPointRead]
    total_forecast_units: float
