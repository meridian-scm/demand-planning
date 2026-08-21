"""Generate prioritized, evidence-backed planning exceptions."""

from datetime import date
from hashlib import sha256
from statistics import fmean

from app.application.forecast_preview import ForecastPreviewService
from app.application.inventory_risk import InventoryRiskService
from app.application.signals import SignalDetectionService
from app.domain import DemandSignal, InventoryRisk, PlanningException
from app.domain.exceptions import ExceptionSeverity, ExceptionStatus, ExceptionType
from app.domain.forecasting import ForecastResult
from app.domain.signals import SignalDirection

FORECAST_BIAS_THRESHOLD = 0.15
FORECAST_UNCERTAINTY_THRESHOLD = 1.0


class PlanningExceptionService:
    """Combine trusted planning analyses into one selected-series attention queue."""

    def __init__(
        self,
        inventory_risk_service: InventoryRiskService,
        signal_service: SignalDetectionService,
        forecast_preview_service: ForecastPreviewService,
    ) -> None:
        self._inventory_risk_service = inventory_risk_service
        self._signal_service = signal_service
        self._forecast_preview_service = forecast_preview_service

    def get_exceptions(
        self,
        store_id: str,
        product_id: str,
        *,
        exception_type: ExceptionType | None = None,
        severity: ExceptionSeverity | None = None,
        status: ExceptionStatus | None = None,
    ) -> tuple[PlanningException, ...]:
        risk = self._inventory_risk_service.get_risk(store_id, product_id)
        signals = self._signal_service.get_signals(store_id, product_id)
        forecast = self._forecast_preview_service.create(
            store_id,
            product_id,
            horizon_months=6,
            interval_level=90,
        ).result
        exceptions = generate_planning_exceptions(risk, signals, forecast)
        return tuple(
            exception
            for exception in exceptions
            if (exception_type is None or exception.exception_type == exception_type)
            and (severity is None or exception.severity == severity)
            and (status is None or exception.status == status)
        )


def generate_planning_exceptions(
    risk: InventoryRisk,
    signals: tuple[DemandSignal, ...],
    forecast: ForecastResult,
) -> tuple[PlanningException, ...]:
    """Apply deterministic exception rules and sort the results by planner priority."""

    exceptions: list[PlanningException] = []
    risk_exception = _risk_exception(risk)
    if risk_exception is not None:
        exceptions.append(risk_exception)

    spike = _latest_signal(signals, "spike")
    if spike is not None:
        exceptions.append(
            _signal_exception(
                risk,
                spike,
                exception_type="demand_spike",
                severity="high" if spike.severity == "warning" else "medium",
                priority_score=80 if spike.severity == "warning" else 70,
                title="Review unusual demand spike",
                description=(
                    "Observed demand materially exceeded its recent baseline and may affect the "
                    "current plan."
                ),
            )
        )

    decline = _latest_decline(signals)
    if decline is not None:
        exceptions.append(
            _signal_exception(
                risk,
                decline,
                exception_type="demand_decline",
                severity="high" if decline.direction == "drop" else "medium",
                priority_score=75 if decline.direction == "drop" else 65,
                title="Review demand decline",
                description=(
                    "Demand is materially below its expected or prior level and may require a "
                    "planning adjustment."
                ),
            )
        )

    uncertainty = _forecast_uncertainty_exception(risk, forecast)
    if uncertainty is not None:
        exceptions.append(uncertainty)
    bias = _forecast_bias_exception(risk, forecast)
    if bias is not None:
        exceptions.append(bias)

    return tuple(
        sorted(
            exceptions,
            key=lambda exception: (
                -exception.priority_score,
                exception.exception_type,
                exception.exception_id,
            ),
        )
    )


def _risk_exception(risk: InventoryRisk) -> PlanningException | None:
    rules: dict[
        str,
        tuple[ExceptionType, ExceptionSeverity, int, str, str, float],
    ] = {
        "stockout": (
            "potential_stockout",
            "critical",
            100,
            "Potential stockout before replenishment",
            "Projected inventory falls below zero before replenishment arrives.",
            0.0,
        ),
        "below_safety_stock": (
            "below_safety_stock",
            "high",
            85,
            "Inventory projected below safety stock",
            "Projected inventory remains nonnegative but does not meet the safety-stock policy.",
            float(risk.safety_stock),
        ),
        "excess": (
            "excess_inventory",
            "medium",
            60,
            "Excess inventory coverage",
            "Projected inventory exceeds the configured maximum coverage threshold.",
            risk.excess_coverage_threshold_months,
        ),
    }
    rule = rules.get(risk.classification)
    if rule is None:
        return None
    exception_type, severity, priority, title, description, threshold = rule
    metric_name = (
        "coverage_months" if risk.classification == "excess" else "projected_inventory_units"
    )
    metric_value = (
        risk.coverage_months
        if risk.classification == "excess" and risk.coverage_months is not None
        else risk.projected_inventory
    )
    return _exception(
        risk,
        exception_type=exception_type,
        severity=severity,
        priority_score=priority,
        relevant_period=risk.replenishment_arrival_at.date(),
        title=title,
        description=description,
        metric_name=metric_name,
        metric_value=metric_value,
        threshold_value=threshold,
        evidence={
            "available_inventory": risk.available_inventory,
            "on_order_due_within_lead_time": risk.on_order_due_within_lead_time,
            "forecast_demand_during_lead_time": risk.forecast_demand_during_lead_time,
            "projected_inventory": risk.projected_inventory,
            "safety_stock": risk.safety_stock,
            "coverage_months": (
                risk.coverage_months if risk.coverage_months is not None else "undefined"
            ),
            "selected_model": risk.selected_model,
        },
        related_risk_id=risk.risk_id,
        related_forecast_id=risk.forecast_id,
    )


def _signal_exception(
    risk: InventoryRisk,
    signal: DemandSignal,
    *,
    exception_type: ExceptionType,
    severity: ExceptionSeverity,
    priority_score: int,
    title: str,
    description: str,
) -> PlanningException:
    relevant_period = signal.period_start
    assert relevant_period is not None
    source = "|".join((signal.store_id, signal.product_id, exception_type, signal.signal_id))
    return PlanningException(
        exception_id=f"exception-{sha256(source.encode()).hexdigest()[:16]}",
        store_id=signal.store_id,
        product_id=signal.product_id,
        sku=signal.sku,
        exception_type=exception_type,
        severity=severity,
        priority_score=priority_score,
        status="open",
        relevant_period=relevant_period,
        title=title,
        description=description,
        metric_name=signal.metric_name,
        metric_value=signal.metric_value,
        threshold_value=signal.threshold_value,
        evidence=dict(signal.evidence),
        related_signal_id=signal.signal_id,
        related_risk_id=None,
        related_forecast_id=None,
        created_at=risk.snapshot_at,
    )


def _forecast_uncertainty_exception(
    risk: InventoryRisk, forecast: ForecastResult
) -> PlanningException | None:
    if not forecast.forecasts:
        return None
    average_width = fmean(point.upper_bound - point.lower_bound for point in forecast.forecasts)
    average_forecast = fmean(point.forecast_value for point in forecast.forecasts)
    width_ratio = average_width / max(average_forecast, 1.0)
    if width_ratio < FORECAST_UNCERTAINTY_THRESHOLD:
        return None
    return _exception(
        risk,
        exception_type="forecast_uncertainty",
        severity="high" if width_ratio >= 2.0 else "medium",
        priority_score=70 if width_ratio >= 2.0 else 55,
        relevant_period=forecast.forecasts[0].period_start,
        title="Forecast uncertainty is high",
        description="The forecast interval is wide relative to expected demand.",
        metric_name="average_interval_width_ratio",
        metric_value=width_ratio,
        threshold_value=FORECAST_UNCERTAINTY_THRESHOLD,
        evidence={
            "average_forecast": average_forecast,
            "average_interval_width": average_width,
            "interval_level": forecast.interval_level,
            "selected_model": forecast.selected_model,
        },
        related_forecast_id=forecast.forecast_id,
    )


def _forecast_bias_exception(
    risk: InventoryRisk, forecast: ForecastResult
) -> PlanningException | None:
    bias = forecast.selected_metrics.bias
    if bias is None or abs(bias) < FORECAST_BIAS_THRESHOLD:
        return None
    return _exception(
        risk,
        exception_type="forecast_bias",
        severity="high" if abs(bias) >= 0.30 else "medium",
        priority_score=68 if abs(bias) >= 0.30 else 52,
        relevant_period=forecast.training_cutoff,
        title="Significant forecast bias",
        description=(
            "Backtesting shows systematic over-forecasting."
            if bias > 0
            else "Backtesting shows systematic under-forecasting."
        ),
        metric_name="forecast_bias",
        metric_value=bias,
        threshold_value=FORECAST_BIAS_THRESHOLD,
        evidence={
            "bias": bias,
            "wape": (
                forecast.selected_metrics.wape
                if forecast.selected_metrics.wape is not None
                else "undefined"
            ),
            "validation_points": forecast.selected_metrics.validation_points,
            "selected_model": forecast.selected_model,
        },
        related_forecast_id=forecast.forecast_id,
    )


def _exception(
    risk: InventoryRisk,
    *,
    exception_type: ExceptionType,
    severity: ExceptionSeverity,
    priority_score: int,
    relevant_period: date,
    title: str,
    description: str,
    metric_name: str,
    metric_value: float,
    threshold_value: float,
    evidence: dict[str, str | int | float],
    related_signal_id: str | None = None,
    related_risk_id: str | None = None,
    related_forecast_id: str | None = None,
) -> PlanningException:
    related_key = related_signal_id or related_risk_id or related_forecast_id or "rule"
    source = "|".join((risk.store_id, risk.product_id, exception_type, related_key))
    return PlanningException(
        exception_id=f"exception-{sha256(source.encode()).hexdigest()[:16]}",
        store_id=risk.store_id,
        product_id=risk.product_id,
        sku=risk.sku,
        exception_type=exception_type,
        severity=severity,
        priority_score=priority_score,
        status="open",
        relevant_period=relevant_period,
        title=title,
        description=description,
        metric_name=metric_name,
        metric_value=metric_value,
        threshold_value=threshold_value,
        evidence=evidence,
        related_signal_id=related_signal_id,
        related_risk_id=related_risk_id,
        related_forecast_id=related_forecast_id,
        created_at=risk.snapshot_at,
    )


def _latest_signal(
    signals: tuple[DemandSignal, ...], direction: SignalDirection
) -> DemandSignal | None:
    candidates = [signal for signal in signals if signal.direction == direction]
    return (
        max(candidates, key=lambda signal: signal.period_start or date.min) if candidates else None
    )


def _latest_decline(signals: tuple[DemandSignal, ...]) -> DemandSignal | None:
    candidates = [signal for signal in signals if signal.direction in ("declining", "drop")]
    return (
        max(candidates, key=lambda signal: signal.period_start or date.min) if candidates else None
    )
