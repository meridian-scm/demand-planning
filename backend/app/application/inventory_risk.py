"""Inventory-position retrieval and lead-time risk calculation."""

from calendar import monthrange
from datetime import date, timedelta
from hashlib import sha256
from statistics import fmean

from app.application.demand_explorer import PlanningDataNotFoundError
from app.application.forecasting import ForecastingEngine
from app.domain import InventoryRisk, InventorySnapshot
from app.domain.forecasting import ForecastResult
from app.domain.inventory import InventoryRiskClassification, InventoryRiskSeverity
from app.ports.repositories.planning import PlanningReadRepository

EXCESS_COVERAGE_THRESHOLD_MONTHS = 6.0
MAXIMUM_RISK_FORECAST_HORIZON = 12


class InventoryRiskUnavailableError(RuntimeError):
    """Raised when inventory risk cannot be calculated from consistent inputs."""


class InventoryRiskService:
    """Orchestrate current position retrieval and a stateless inventory-risk forecast."""

    def __init__(
        self,
        repository: PlanningReadRepository,
        forecasting_engine: ForecastingEngine,
        *,
        excess_coverage_threshold_months: float = EXCESS_COVERAGE_THRESHOLD_MONTHS,
    ) -> None:
        self._repository = repository
        self._forecasting_engine = forecasting_engine
        self._excess_coverage_threshold_months = excess_coverage_threshold_months

    def get_position(self, store_id: str, product_id: str) -> InventorySnapshot:
        position = self._repository.get_inventory_snapshot(store_id, product_id)
        if position is None:
            raise PlanningDataNotFoundError(
                f"No inventory position exists for store {store_id!r} and product {product_id!r}."
            )
        return position

    def get_risk(self, store_id: str, product_id: str) -> InventoryRisk:
        position = self.get_position(store_id, product_id)
        policy = self._repository.get_store_product(store_id, product_id)
        observations = self._repository.get_demand_series(store_id, product_id)
        if policy is None or not observations:
            raise PlanningDataNotFoundError(
                f"No planning data exists for store {store_id!r} and product {product_id!r}."
            )
        if (
            policy.lead_time_days != position.lead_time_days
            or policy.safety_stock != position.safety_stock
        ):
            raise InventoryRiskUnavailableError(
                "Inventory snapshot policy does not match the Store + SKU planning policy."
            )

        training_cutoff = observations[-1].period_start
        forecast_start = _add_months(training_cutoff, 1)
        horizon = _required_forecast_horizon(position, forecast_start)
        if horizon > MAXIMUM_RISK_FORECAST_HORIZON:
            raise InventoryRiskUnavailableError(
                "Inventory lead-time window exceeds the supported 12-month forecast horizon."
            )
        forecast = self._forecasting_engine.run(
            [observation.demand_units for observation in observations],
            training_cutoff=training_cutoff,
            horizon=horizon,
            interval_level=90,
        )
        return calculate_inventory_risk(
            position,
            forecast,
            excess_coverage_threshold_months=self._excess_coverage_threshold_months,
        )


def calculate_inventory_risk(
    position: InventorySnapshot,
    forecast: ForecastResult,
    *,
    excess_coverage_threshold_months: float = EXCESS_COVERAGE_THRESHOLD_MONTHS,
) -> InventoryRisk:
    """Project stock at lead-time arrival using calendar-day forecast allocation."""

    if excess_coverage_threshold_months <= 0:
        raise ValueError("excess coverage threshold must be positive")
    lead_time_start = position.snapshot_at.date()
    arrival_at = position.snapshot_at + timedelta(days=position.lead_time_days)
    arrival_date = arrival_at.date()
    forecast_demand = 0.0
    covered_days = 0

    for point in forecast.forecasts:
        month_start = point.period_start
        month_end = _add_months(month_start, 1)
        overlap_start = max(lead_time_start, month_start)
        overlap_end = min(arrival_date, month_end)
        overlap_days = max(0, (overlap_end - overlap_start).days)
        if overlap_days:
            days_in_month = monthrange(month_start.year, month_start.month)[1]
            forecast_demand += point.forecast_value * overlap_days / days_in_month
            covered_days += overlap_days

    if covered_days != position.lead_time_days:
        raise InventoryRiskUnavailableError(
            "Forecast points do not completely cover the inventory lead-time window."
        )

    available_inventory = position.on_hand - position.allocated
    projected_inventory = (
        available_inventory + position.on_order_due_within_lead_time - forecast_demand
    )
    average_monthly_forecast = (
        fmean(point.forecast_value for point in forecast.forecasts) if forecast.forecasts else 0.0
    )
    coverage_months = (
        max(0.0, projected_inventory) / average_monthly_forecast
        if average_monthly_forecast > 0
        else None
    )
    classification, severity = _classify_risk(
        projected_inventory,
        position.safety_stock,
        coverage_months,
        excess_coverage_threshold_months,
    )
    identity = "|".join(
        (
            position.store_id,
            position.product_id,
            position.snapshot_at.isoformat(),
            forecast.forecast_id,
            classification,
        )
    )
    return InventoryRisk(
        risk_id=f"risk-{sha256(identity.encode()).hexdigest()[:16]}",
        store_id=position.store_id,
        product_id=position.product_id,
        sku=position.sku,
        classification=classification,
        severity=severity,
        snapshot_at=position.snapshot_at,
        replenishment_arrival_at=arrival_at,
        available_inventory=available_inventory,
        on_order_due_within_lead_time=position.on_order_due_within_lead_time,
        forecast_demand_during_lead_time=forecast_demand,
        projected_inventory=projected_inventory,
        safety_stock=position.safety_stock,
        coverage_months=coverage_months,
        excess_coverage_threshold_months=excess_coverage_threshold_months,
        selected_model=forecast.selected_model,
        forecast_id=forecast.forecast_id,
        training_cutoff=forecast.training_cutoff,
        forecast_horizon_months=forecast.horizon_months,
    )


def _classify_risk(
    projected_inventory: float,
    safety_stock: int,
    coverage_months: float | None,
    excess_coverage_threshold_months: float,
) -> tuple[InventoryRiskClassification, InventoryRiskSeverity]:
    if projected_inventory < 0:
        return "stockout", "warning"
    if projected_inventory < safety_stock:
        return "below_safety_stock", "watch"
    if coverage_months is not None and coverage_months > excess_coverage_threshold_months:
        return "excess", "watch"
    return "healthy", "info"


def _required_forecast_horizon(position: InventorySnapshot, forecast_start: date) -> int:
    lead_time_start = position.snapshot_at.date()
    if lead_time_start < forecast_start:
        raise InventoryRiskUnavailableError(
            "Inventory snapshot predates the first available forecast period."
        )
    final_covered_date = lead_time_start + timedelta(days=max(position.lead_time_days - 1, 0))
    month_difference = (
        (final_covered_date.year - forecast_start.year) * 12
        + final_covered_date.month
        - forecast_start.month
    )
    return max(1, month_difference + 1)


def _add_months(period: date, months: int) -> date:
    month_index = period.year * 12 + period.month - 1 + months
    return date(month_index // 12, month_index % 12 + 1, 1)
