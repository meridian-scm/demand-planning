"""HTTP schemas for the portfolio Overview."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict


class OverviewDemandPointResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    period_start: date
    actual_units: int | None
    forecast_units: float | None


class OverviewRiskCountsResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    stockout: int
    below_safety_stock: int
    healthy: int
    excess: int
    unavailable: int


class OverviewExceptionResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    exception_id: str
    store_id: str
    store_name: str
    product_id: str
    sku: str
    product_name: str
    category: str
    exception_type: Literal[
        "potential_stockout",
        "below_safety_stock",
        "excess_inventory",
        "forecast_uncertainty",
        "forecast_bias",
    ]
    severity: Literal["medium", "high", "critical"]
    priority_score: int
    title: str
    description: str
    metric_name: str
    metric_value: float
    threshold_value: float
    selected_model: str


class PortfolioOverviewResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    data_version: str
    training_cutoff: date
    horizon_months: int
    store_id: str | None
    store_name: str
    series_count: int
    recent_12_month_demand: int
    prior_12_month_demand: int
    demand_change: float | None
    forecast_horizon_demand: float
    median_series_wape: float | None
    median_series_mase: float | None
    median_absolute_bias: float | None
    weighted_interval_coverage: float | None
    risk_counts: OverviewRiskCountsResponse
    timeline: list[OverviewDemandPointResponse]
    priority_exceptions: list[OverviewExceptionResponse]
