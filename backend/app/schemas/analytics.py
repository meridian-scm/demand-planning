"""Dashboard and analytics response schemas."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from app.schemas.exception import ExceptionRead
from app.schemas.product import ProductRead


class DashboardSummary(BaseModel):
    """Headline KPI tiles."""

    active_products: int
    history_total_units: float
    forecast_total_units: float
    forecast_periods: int
    demand_growth_pct: float | None
    open_exceptions: int
    critical_exceptions: int
    average_wape: float | None
    latest_run_id: int | None


class HistoryPoint(BaseModel):
    period_start: date
    units: float


class ForecastSeriesPoint(BaseModel):
    period_start: date
    forecast_units: float
    lower_bound_units: float | None
    upper_bound_units: float | None


class DemandTimeline(BaseModel):
    """Actuals and forecast on one continuous timeline."""

    history: list[HistoryPoint]
    forecast: list[ForecastSeriesPoint]
    run_id: int | None


class TrendEntry(BaseModel):
    product_id: int
    sku: str
    name: str
    category: str
    recent_units: float
    prior_units: float
    growth_pct: float


class TrendsResponse(BaseModel):
    growing: list[TrendEntry]
    declining: list[TrendEntry]
    window_periods: int


class CategoryBreakdown(BaseModel):
    category: str
    history_units: float
    forecast_units: float


class ExceptionBreakdown(BaseModel):
    exception_type: str
    severity: str
    count: int


class ProductDetail(BaseModel):
    """Everything the product drill-down page renders."""

    product: ProductRead
    timeline: DemandTimeline
    exceptions: list[ExceptionRead]
    history_total_units: float
    forecast_total_units: float
    model_used: str | None
    wape: float | None
    mape: float | None
