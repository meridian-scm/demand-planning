"""HTTP schemas for catalog and demand-planning reads."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StoreResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    store_id: str
    store_code: str
    store_name: str
    city: str
    region: str
    country: str
    timezone: str


class ProductResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    product_id: str
    sku: str
    product_name: str
    category: str
    subcategory: str
    brand: str
    unit_cost: Decimal
    unit_price: Decimal


class PlanningPolicyResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    lead_time_days: int
    safety_stock: int
    reorder_point: int
    minimum_order_quantity: int
    order_multiple: int
    service_level_target: float


class DemandPointResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    period_start: date
    demand_units: int


class DemandSummaryResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    period_start: date
    period_end: date
    total_units: int
    average_monthly_units: float
    minimum_monthly_units: int
    maximum_monthly_units: int
    zero_demand_months: int


class DemandSeriesResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    store_id: str
    product: ProductResponse
    policy: PlanningPolicyResponse
    observations: list[DemandPointResponse]
    summary: DemandSummaryResponse


class ForecastPreviewRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    store_id: str = Field(min_length=1)
    product_id: str = Field(min_length=1)
    horizon_months: int = Field(default=6, ge=1, le=12)
    interval_level: int = Field(default=90, ge=50, le=99)


class ForecastMetricsResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    wape: float | None
    mase: float | None
    rmse: float
    bias: float | None
    interval_coverage: float | None
    validation_points: int


class ModelEvaluationResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    model_name: str
    status: Literal["succeeded", "failed"]
    validation_origins: int
    metrics: ForecastMetricsResponse | None
    failure_detail: str | None


class ForecastPointResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    period_start: date
    forecast_value: float
    lower_bound: float
    upper_bound: float
    horizon: int


class ForecastPreviewResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    forecast_id: str
    store_id: str
    product: ProductResponse
    selected_model: str
    training_cutoff: date
    horizon_months: int
    interval_level: int
    intermittent_demand: bool
    validation_origins: int
    selected_metrics: ForecastMetricsResponse
    evaluations: list[ModelEvaluationResponse]
    forecasts: list[ForecastPointResponse]


class DemandSignalResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    signal_id: str
    store_id: str
    product_id: str
    sku: str
    signal_type: Literal["trend", "volatility", "seasonality", "anomaly"]
    direction: Literal["growing", "declining", "stable", "volatile", "seasonal", "spike", "drop"]
    severity: Literal["info", "watch", "warning"]
    period_start: date | None
    title: str
    description: str
    metric_name: str
    metric_value: float
    baseline_value: float | None
    threshold_value: float
    evidence: dict[str, str | int | float]


class InventoryPositionResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    store_id: str
    product_id: str
    sku: str
    snapshot_at: datetime
    on_hand: int
    allocated: int
    on_order: int
    on_order_due_within_lead_time: int
    next_expected_receipt_at: datetime | None
    lead_time_days: int
    safety_stock: int


class InventoryRiskResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    risk_id: str
    store_id: str
    product_id: str
    sku: str
    classification: Literal["stockout", "below_safety_stock", "healthy", "excess"]
    severity: Literal["info", "watch", "warning"]
    snapshot_at: datetime
    replenishment_arrival_at: datetime
    available_inventory: int
    on_order_due_within_lead_time: int
    forecast_demand_during_lead_time: float
    projected_inventory: float
    safety_stock: int
    coverage_months: float | None
    excess_coverage_threshold_months: float
    selected_model: str
    forecast_id: str
    training_cutoff: date
    forecast_horizon_months: int


class PlanningExceptionResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    exception_id: str
    store_id: str
    product_id: str
    sku: str
    exception_type: Literal[
        "potential_stockout",
        "below_safety_stock",
        "excess_inventory",
        "demand_spike",
        "demand_decline",
        "forecast_uncertainty",
        "forecast_bias",
    ]
    severity: Literal["medium", "high", "critical"]
    priority_score: int
    status: Literal["open", "acknowledged", "resolved", "dismissed"]
    relevant_period: date
    title: str
    description: str
    metric_name: str
    metric_value: float
    threshold_value: float
    evidence: dict[str, str | int | float]
    related_signal_id: str | None
    related_risk_id: str | None
    related_forecast_id: str | None
    created_at: datetime
