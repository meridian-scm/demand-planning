"""Unit tests for the planning exception detector."""

from __future__ import annotations

from datetime import date

import pytest

from app.models.enums import ExceptionType
from app.services.exceptions import ExceptionDetector, InventoryPosition
from app.services.forecasting.types import (
    AccuracyMetrics,
    ForecastPoint,
    ForecastResult,
    Observation,
)

pytestmark = pytest.mark.unit


def series(*values: float, start_year: int = 2025, start_month: int = 1) -> list[Observation]:
    result = []
    year, month = start_year, start_month
    for value in values:
        result.append(Observation(period_start=date(year, month, 1), units=value))
        month += 1
        if month > 12:
            month = 1
            year += 1
    return result


def make_forecast(*forecast_units: float, wape: float | None = 10.0) -> ForecastResult:
    points = [
        ForecastPoint(
            period_start=date(2025, 8 + index, 1),
            forecast_units=value,
            lower_bound_units=max(0.0, value - 10),
            upper_bound_units=value + 10,
        )
        for index, value in enumerate(forecast_units)
    ]
    return ForecastResult(
        model_used="linear_trend",
        points=points,
        metrics=AccuracyMetrics(mape=wape, wape=wape, rmse=1.0),
    )


class TestDemandSpike:
    def test_detects_large_upward_deviation(self) -> None:
        detector = ExceptionDetector(spike_threshold_pct=25, zscore_threshold=1.0)
        history = series(100, 102, 98, 260)  # last period spikes hard
        found = detector.detect(product_name="Widget", observations=history)
        types = [item.exception_type for item in found]
        assert ExceptionType.DEMAND_SPIKE.value in types

    def test_no_spike_within_normal_range(self) -> None:
        detector = ExceptionDetector(spike_threshold_pct=25, zscore_threshold=1.0)
        history = series(100, 102, 98, 105)
        found = detector.detect(product_name="Widget", observations=history)
        assert not any(item.exception_type == ExceptionType.DEMAND_SPIKE.value for item in found)

    def test_severity_scales_with_magnitude(self) -> None:
        detector = ExceptionDetector(spike_threshold_pct=25, zscore_threshold=1.0)
        history = series(98, 100, 102, 400)  # +300%, slight baseline variance so std != 0
        found = [
            item
            for item in detector.detect(product_name="Widget", observations=history)
            if item.exception_type == ExceptionType.DEMAND_SPIKE.value
        ]
        assert found and found[0].severity == "critical"


class TestDemandDrop:
    def test_detects_large_downward_deviation(self) -> None:
        detector = ExceptionDetector(drop_threshold_pct=25, zscore_threshold=1.0)
        history = series(100, 98, 102, 20)
        found = detector.detect(product_name="Widget", observations=history)
        assert any(item.exception_type == ExceptionType.DEMAND_DROP.value for item in found)

    def test_zero_baseline_is_skipped_safely(self) -> None:
        detector = ExceptionDetector()
        history = series(0, 0, 0, 50)
        # Should not raise a ZeroDivisionError.
        detector.detect(product_name="Widget", observations=history)


class TestStockoutRisk:
    def test_low_cover_triggers_stockout(self) -> None:
        detector = ExceptionDetector(stockout_cover_periods=1.0)
        forecast = make_forecast(100, 100, 100)
        inventory = InventoryPosition(available_units=50, lead_time_days=14, safety_stock_units=0)
        found = detector.detect(
            product_name="Widget",
            observations=series(100, 100, 100, 100),
            forecast=forecast,
            inventory=inventory,
        )
        assert any(item.exception_type == ExceptionType.STOCKOUT_RISK.value for item in found)

    def test_healthy_cover_does_not_trigger(self) -> None:
        detector = ExceptionDetector(stockout_cover_periods=1.0, excess_cover_periods=4.0)
        forecast = make_forecast(100, 100, 100)
        inventory = InventoryPosition(available_units=200, lead_time_days=14, safety_stock_units=0)
        found = detector.detect(
            product_name="Widget",
            observations=series(100, 100, 100, 100),
            forecast=forecast,
            inventory=inventory,
        )
        assert not any(
            item.exception_type in (ExceptionType.STOCKOUT_RISK.value, ExceptionType.EXCESS_INVENTORY.value)
            for item in found
        )


class TestExcessInventory:
    def test_high_cover_triggers_excess(self) -> None:
        detector = ExceptionDetector(excess_cover_periods=2.0)
        forecast = make_forecast(50, 50, 50)
        inventory = InventoryPosition(available_units=1000, lead_time_days=14, safety_stock_units=0)
        found = detector.detect(
            product_name="Widget",
            observations=series(50, 50, 50, 50),
            forecast=forecast,
            inventory=inventory,
        )
        assert any(item.exception_type == ExceptionType.EXCESS_INVENTORY.value for item in found)

    def test_safety_stock_reduces_available_for_cover_calc(self) -> None:
        detector = ExceptionDetector(stockout_cover_periods=1.0)
        forecast = make_forecast(100, 100, 100)
        # 110 on hand but 100 reserved as safety stock -> only 10 net available.
        inventory = InventoryPosition(available_units=110, lead_time_days=14, safety_stock_units=100)
        found = detector.detect(
            product_name="Widget",
            observations=series(100, 100, 100, 100),
            forecast=forecast,
            inventory=inventory,
        )
        assert any(item.exception_type == ExceptionType.STOCKOUT_RISK.value for item in found)


class TestForecastAnomaly:
    def test_high_wape_flags_low_confidence(self) -> None:
        detector = ExceptionDetector()
        forecast = make_forecast(100, 100, wape=65.0)
        found = detector.detect(
            product_name="Widget", observations=series(100, 100, 100, 100), forecast=forecast
        )
        assert any(item.exception_type == ExceptionType.FORECAST_ANOMALY.value for item in found)

    def test_low_wape_does_not_flag(self) -> None:
        detector = ExceptionDetector()
        forecast = make_forecast(100, 100, wape=5.0)
        found = detector.detect(
            product_name="Widget", observations=series(100, 100, 100, 100), forecast=forecast
        )
        assert not any(item.exception_type == ExceptionType.FORECAST_ANOMALY.value for item in found)


class TestVolatility:
    def test_flags_erratic_new_product(self) -> None:
        detector = ExceptionDetector()
        history = series(10, 90, 5, 120)
        found = detector.detect(product_name="New Widget", observations=history)
        assert any(item.exception_type == ExceptionType.NEW_PRODUCT_VOLATILITY.value for item in found)

    def test_established_product_is_not_flagged_regardless_of_variance(self) -> None:
        detector = ExceptionDetector()
        # 7 periods, above the NEW_PRODUCT_PERIODS window, so volatility rule
        # should not fire even though the series is noisy.
        history = series(10, 90, 5, 120, 10, 90, 5)
        found = detector.detect(product_name="Old Widget", observations=history)
        assert not any(item.exception_type == ExceptionType.NEW_PRODUCT_VOLATILITY.value for item in found)


class TestNoInventoryProvided:
    def test_inventory_rules_are_skipped_without_a_snapshot(self) -> None:
        detector = ExceptionDetector()
        forecast = make_forecast(100, 100)
        found = detector.detect(
            product_name="Widget",
            observations=series(100, 100, 100, 100),
            forecast=forecast,
            inventory=None,
        )
        assert not any(
            item.exception_type in (ExceptionType.STOCKOUT_RISK.value, ExceptionType.EXCESS_INVENTORY.value)
            for item in found
        )
