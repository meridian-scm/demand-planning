"""Unit tests for planning-exception rules and lifecycle."""

from datetime import UTC, date, datetime

import pytest
from app.application.planning_exceptions import generate_planning_exceptions
from app.domain import DemandSignal, InventoryRisk
from app.domain.forecasting import ForecastMetrics, ForecastPoint, ForecastResult
from app.domain.inventory import InventoryRiskClassification, InventoryRiskSeverity
from app.domain.signals import SignalDirection


def _risk(classification: InventoryRiskClassification = "stockout") -> InventoryRisk:
    severity: InventoryRiskSeverity = "warning" if classification == "stockout" else "watch"
    return InventoryRisk(
        risk_id="risk-test-1",
        store_id="store-001",
        product_id="product-00001",
        sku="SKU-00001",
        classification=classification,
        severity=severity,
        snapshot_at=datetime(2026, 1, 15, 12, tzinfo=UTC),
        replenishment_arrival_at=datetime(2026, 1, 29, 12, tzinfo=UTC),
        available_inventory=40,
        on_order_due_within_lead_time=10,
        forecast_demand_during_lead_time=90,
        projected_inventory=-40 if classification == "stockout" else 20,
        safety_stock=30,
        coverage_months=7 if classification == "excess" else 0.2,
        excess_coverage_threshold_months=6,
        selected_model="AutoETS",
        forecast_id="preview-risk-1",
        training_cutoff=date(2025, 12, 1),
        forecast_horizon_months=1,
    )


def _signal(direction: SignalDirection, period: date) -> DemandSignal:
    return DemandSignal(
        signal_id=f"signal-{direction}",
        store_id="store-001",
        product_id="product-00001",
        sku="SKU-00001",
        signal_type="anomaly",
        direction=direction,
        severity="warning",
        period_start=period,
        title=f"Demand {direction}",
        description="Material movement.",
        metric_name="robust_anomaly_score",
        metric_value=5.5,
        baseline_value=100,
        threshold_value=3.5,
        evidence={"observed_demand": 200, "baseline": 100},
    )


def _forecast(*, bias: float = -0.35, interval_width: float = 250) -> ForecastResult:
    return ForecastResult(
        forecast_id="preview-six-month-1",
        selected_model="AutoETS",
        training_cutoff=date(2025, 12, 1),
        horizon_months=6,
        interval_level=90,
        intermittent_demand=False,
        validation_origins=4,
        selected_metrics=ForecastMetrics(
            wape=0.2,
            mase=1.1,
            rmse=20,
            bias=bias,
            interval_coverage=0.8,
            validation_points=24,
        ),
        evaluations=(),
        forecasts=tuple(
            ForecastPoint(
                period_start=date(2026, month, 1),
                forecast_value=100,
                lower_bound=0,
                upper_bound=interval_width,
                horizon=month,
            )
            for month in range(1, 7)
        ),
    )


def test_exceptions_combine_risk_signals_bias_and_uncertainty_in_priority_order() -> None:
    exceptions = generate_planning_exceptions(
        _risk(),
        (_signal("spike", date(2025, 10, 1)), _signal("drop", date(2025, 11, 1))),
        _forecast(),
    )

    assert [exception.exception_type for exception in exceptions] == [
        "potential_stockout",
        "demand_spike",
        "demand_decline",
        "forecast_uncertainty",
        "forecast_bias",
    ]
    assert [exception.priority_score for exception in exceptions] == sorted(
        (exception.priority_score for exception in exceptions), reverse=True
    )
    assert exceptions[0].severity == "critical"
    assert exceptions[0].related_risk_id == "risk-test-1"
    assert exceptions[1].related_signal_id == "signal-spike"
    assert exceptions[-1].related_forecast_id == "preview-six-month-1"
    assert all(exception.status == "open" for exception in exceptions)


def test_healthy_stable_reliable_series_has_no_exception() -> None:
    risk = _risk("healthy")
    stable_signal = DemandSignal(
        signal_id="signal-stable",
        store_id=risk.store_id,
        product_id=risk.product_id,
        sku=risk.sku,
        signal_type="trend",
        direction="stable",
        severity="info",
        period_start=date(2025, 12, 1),
        title="Stable",
        description="Stable demand.",
        metric_name="change",
        metric_value=0,
        baseline_value=100,
        threshold_value=0.1,
        evidence={},
    )

    exceptions = generate_planning_exceptions(
        risk,
        (stable_signal,),
        _forecast(bias=0.02, interval_width=40),
    )

    assert exceptions == ()


def test_exception_lifecycle_allows_only_simple_review_transitions() -> None:
    exception = generate_planning_exceptions(_risk(), (), _forecast(bias=0, interval_width=40))[0]

    acknowledged = exception.transition_to("acknowledged")
    resolved = acknowledged.transition_to("resolved")

    assert acknowledged.status == "acknowledged"
    assert resolved.status == "resolved"
    with pytest.raises(ValueError, match="Cannot transition"):
        exception.transition_to("resolved")
    with pytest.raises(ValueError, match="Cannot transition"):
        resolved.transition_to("open")


def test_exception_ids_are_deterministic() -> None:
    first = generate_planning_exceptions(_risk(), (), _forecast())
    second = generate_planning_exceptions(_risk(), (), _forecast())

    assert first == second
    assert all(exception.exception_id.startswith("exception-") for exception in first)
