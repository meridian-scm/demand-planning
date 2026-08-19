"""Enumerations shared by the ORM models and the API schemas."""

from __future__ import annotations

from enum import StrEnum


class ForecastModel(StrEnum):
    """Forecasting algorithms available to the engine."""

    NAIVE = "naive"
    MOVING_AVERAGE = "moving_average"
    LINEAR_TREND = "linear_trend"
    HOLT_LINEAR = "holt_linear"
    HOLT_WINTERS = "holt_winters"
    SEASONAL_NAIVE = "seasonal_naive"
    AUTO = "auto"


class ExceptionType(StrEnum):
    """Categories of planning exception surfaced to planners."""

    DEMAND_SPIKE = "demand_spike"
    DEMAND_DROP = "demand_drop"
    STOCKOUT_RISK = "stockout_risk"
    EXCESS_INVENTORY = "excess_inventory"
    FORECAST_ANOMALY = "forecast_anomaly"
    NEW_PRODUCT_VOLATILITY = "new_product_volatility"


class ExceptionSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ExceptionStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class InsightScope(StrEnum):
    """What an AI-generated narrative is talking about."""

    PORTFOLIO = "portfolio"
    PRODUCT = "product"
    EXCEPTION = "exception"
