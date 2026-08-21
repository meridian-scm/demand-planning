"""Unit tests for lead-time inventory-risk calculations."""

from datetime import UTC, date, datetime

import pytest
from app.application.inventory_risk import calculate_inventory_risk
from app.domain import InventorySnapshot
from app.domain.forecasting import ForecastMetrics, ForecastPoint, ForecastResult


def _position(
    *,
    on_hand: int,
    allocated: int = 10,
    on_order_due: int = 0,
    lead_time_days: int = 7,
    safety_stock: int = 30,
    snapshot_at: datetime = datetime(2026, 1, 15, tzinfo=UTC),
) -> InventorySnapshot:
    return InventorySnapshot(
        store_id="store-001",
        product_id="product-00001",
        sku="SKU-00001",
        snapshot_at=snapshot_at,
        on_hand=on_hand,
        allocated=allocated,
        on_order=on_order_due,
        on_order_due_within_lead_time=on_order_due,
        next_expected_receipt_at=None,
        lead_time_days=lead_time_days,
        safety_stock=safety_stock,
    )


def _forecast(values: list[float]) -> ForecastResult:
    points = tuple(
        ForecastPoint(
            period_start=date(2026 + index // 12, index % 12 + 1, 1),
            forecast_value=value,
            lower_bound=max(0, value - 20),
            upper_bound=value + 20,
            horizon=index + 1,
        )
        for index, value in enumerate(values)
    )
    return ForecastResult(
        forecast_id="preview-inventory-test",
        selected_model="Naive",
        training_cutoff=date(2025, 12, 1),
        horizon_months=len(points),
        interval_level=90,
        intermittent_demand=False,
        validation_origins=2,
        selected_metrics=ForecastMetrics(
            wape=0.1,
            mase=0.9,
            rmse=10,
            bias=0.01,
            interval_coverage=0.9,
            validation_points=12,
        ),
        evaluations=(),
        forecasts=points,
    )


@pytest.mark.parametrize(
    ("on_hand", "expected"),
    [(50, "stockout"), (100, "below_safety_stock"), (150, "healthy"), (2100, "excess")],
)
def test_projected_inventory_classifications(on_hand: int, expected: str) -> None:
    risk = calculate_inventory_risk(_position(on_hand=on_hand), _forecast([310]))

    assert risk.classification == expected
    assert risk.forecast_demand_during_lead_time == pytest.approx(70)
    assert risk.projected_inventory == pytest.approx(on_hand - 10 - 70)


def test_on_order_due_within_lead_time_reduces_stockout_risk() -> None:
    without_receipt = calculate_inventory_risk(_position(on_hand=50), _forecast([310]))
    with_receipt = calculate_inventory_risk(
        _position(on_hand=50, on_order_due=100), _forecast([310])
    )

    assert without_receipt.classification == "stockout"
    assert with_receipt.classification == "healthy"
    assert with_receipt.projected_inventory == pytest.approx(70)


def test_monthly_forecasts_are_allocated_across_calendar_day_overlap() -> None:
    risk = calculate_inventory_risk(
        _position(
            on_hand=500,
            lead_time_days=30,
            snapshot_at=datetime(2026, 1, 20, tzinfo=UTC),
        ),
        _forecast([310, 280]),
    )

    assert risk.forecast_demand_during_lead_time == pytest.approx(300)
    assert risk.replenishment_arrival_at == datetime(2026, 2, 19, tzinfo=UTC)


def test_incomplete_forecast_window_fails_instead_of_understating_demand() -> None:
    with pytest.raises(RuntimeError, match="completely cover"):
        calculate_inventory_risk(
            _position(on_hand=500, lead_time_days=60),
            _forecast([310]),
        )
