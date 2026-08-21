"""Tests for honest portfolio metrics, risk exposure, and prioritization."""

from dataclasses import replace
from datetime import UTC, date, datetime

from app.application.overview import OverviewService
from app.domain import ForecastRun, OverviewDemandPoint, OverviewSeriesEvidence


class _Runs:
    run = ForecastRun(
        run_id="forecast-test",
        data_version="test-v1",
        status="completed",
        created_at=datetime(2026, 1, 15, tzinfo=UTC),
        training_cutoff=date(2025, 12, 1),
        horizon_months=6,
        interval_level=90,
        series_count=4,
        successful_series_count=4,
        failed_series_count=0,
        evaluation_count=4,
        forecast_count=24,
    )

    def list_runs(self) -> tuple[ForecastRun, ...]:
        return (self.run,)

    def get_run(self, run_id: str) -> ForecastRun | None:
        return self.run if run_id == self.run.run_id else None

    def list_series(self, *_: object, **__: object) -> tuple[()]:
        return ()

    def get_evaluations(self, *_: object) -> tuple[()]:
        return ()

    def get_forecasts(self, *_: object) -> tuple[()]:
        return ()


class _OverviewInputs:
    base = OverviewSeriesEvidence(
        store_id="store-001",
        store_name="Toronto Central",
        product_id="product-001",
        sku="SKU-001",
        product_name="Product 1",
        category="Grocery",
        selected_model="Naive",
        wape=0.2,
        mase=0.9,
        bias=0.05,
        interval_coverage=0.9,
        validation_points=24,
        available_inventory=100,
        on_order_due_within_lead_time=0,
        safety_stock=25,
        lead_time_days=10,
        covered_lead_time_days=10,
        forecast_demand_during_lead_time=40,
        average_monthly_forecast=100,
        average_interval_width=40,
    )

    def get_timeline(self, run_id: str, *, store_id: str | None) -> tuple[OverviewDemandPoint, ...]:
        del run_id, store_id
        actuals = tuple(
            OverviewDemandPoint(date(2024 + index // 12, index % 12 + 1, 1), 50 + index * 5, None)
            for index in range(24)
        )
        forecasts = tuple(
            OverviewDemandPoint(date(2026, index + 1, 1), None, 100.0) for index in range(6)
        )
        return actuals + forecasts

    def get_series_evidence(
        self, run_id: str, *, store_id: str | None
    ) -> tuple[OverviewSeriesEvidence, ...]:
        del run_id, store_id
        return (
            replace(
                self.base,
                available_inventory=10,
                forecast_demand_during_lead_time=50,
                bias=-0.35,
            ),
            replace(
                self.base,
                product_id="product-002",
                sku="SKU-002",
                available_inventory=30,
                forecast_demand_during_lead_time=20,
            ),
            replace(self.base, product_id="product-003", sku="SKU-003"),
            replace(
                self.base,
                product_id="product-004",
                sku="SKU-004",
                available_inventory=800,
            ),
        )


def test_overview_calculates_risks_reliability_and_priority_without_refitting() -> None:
    result = OverviewService(_Runs(), _OverviewInputs()).get_overview(
        run_id=None,
        store_id=None,
        exception_limit=3,
    )

    assert result.series_count == 4
    assert result.recent_12_month_demand > result.prior_12_month_demand
    assert result.forecast_horizon_demand == 600
    assert result.median_series_wape == 0.2
    assert result.weighted_interval_coverage == 0.9
    assert result.risk_counts.stockout == 1
    assert result.risk_counts.below_safety_stock == 1
    assert result.risk_counts.healthy == 1
    assert result.risk_counts.excess == 1
    assert len(result.priority_exceptions) == 3
    assert result.priority_exceptions[0].exception_type == "potential_stockout"
    assert result.priority_exceptions[0].severity == "critical"
