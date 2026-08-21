"""Storage-independent portfolio overview read models."""

from dataclasses import dataclass
from datetime import date
from typing import Literal

OverviewExceptionType = Literal[
    "potential_stockout",
    "below_safety_stock",
    "excess_inventory",
    "forecast_uncertainty",
    "forecast_bias",
]
OverviewExceptionSeverity = Literal["medium", "high", "critical"]


@dataclass(frozen=True, slots=True)
class OverviewDemandPoint:
    period_start: date
    actual_units: int | None
    forecast_units: float | None


@dataclass(frozen=True, slots=True)
class OverviewSeriesEvidence:
    store_id: str
    store_name: str
    product_id: str
    sku: str
    product_name: str
    category: str
    selected_model: str
    wape: float | None
    mase: float | None
    bias: float | None
    interval_coverage: float | None
    validation_points: int | None
    available_inventory: int
    on_order_due_within_lead_time: int
    safety_stock: int
    lead_time_days: int
    covered_lead_time_days: int
    forecast_demand_during_lead_time: float
    average_monthly_forecast: float
    average_interval_width: float


@dataclass(frozen=True, slots=True)
class OverviewException:
    exception_id: str
    store_id: str
    store_name: str
    product_id: str
    sku: str
    product_name: str
    category: str
    exception_type: OverviewExceptionType
    severity: OverviewExceptionSeverity
    priority_score: int
    title: str
    description: str
    metric_name: str
    metric_value: float
    threshold_value: float
    selected_model: str


@dataclass(frozen=True, slots=True)
class OverviewRiskCounts:
    stockout: int
    below_safety_stock: int
    healthy: int
    excess: int
    unavailable: int


@dataclass(frozen=True, slots=True)
class PortfolioOverview:
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
    risk_counts: OverviewRiskCounts
    timeline: tuple[OverviewDemandPoint, ...]
    priority_exceptions: tuple[OverviewException, ...]
