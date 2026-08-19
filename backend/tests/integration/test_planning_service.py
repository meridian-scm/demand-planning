"""Integration tests for PlanningService — the DB-backed orchestration layer."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models import Forecast, InventorySnapshot, PlanningException, Product, SalesHistory
from app.models.enums import ExceptionStatus
from app.services.ai import InsightService, TemplateProvider
from app.services.forecasting import ForecastEngine
from app.services.planning import PlanningService

pytestmark = pytest.mark.integration


def _add_history(db: Session, product: Product, values: list[int], start=(2025, 1)) -> None:
    year, month = start
    for value in values:
        db.add(SalesHistory(product_id=product.id, period_start=date(year, month, 1), units_sold=value))
        month += 1
        if month > 12:
            month = 1
            year += 1
    db.commit()


@pytest.fixture()
def planning_service(db_session: Session) -> PlanningService:
    return PlanningService(
        db_session,
        engine=ForecastEngine(min_history_periods=3, holdout_periods=1),
        insights=InsightService(primary=None, fallback=TemplateProvider(), ai_enabled=False),
    )


class TestRunForecast:
    def test_forecasts_all_active_products(
        self, db_session: Session, planning_service: PlanningService
    ) -> None:
        p1 = Product(sku="SKU-1", name="A", category="Cat")
        p2 = Product(sku="SKU-2", name="B", category="Cat")
        db_session.add_all([p1, p2])
        db_session.commit()
        _add_history(db_session, p1, [100, 110, 120, 130])
        _add_history(db_session, p2, [50, 55, 60, 65])

        run = planning_service.run_forecast(horizon=2)

        assert run.products_forecasted == 2
        assert run.products_skipped == 0
        forecasts = db_session.execute(select(Forecast).where(Forecast.run_id == run.id)).scalars().all()
        assert len(forecasts) == 4  # 2 products x 2 horizon periods

    def test_skips_products_with_too_little_history(
        self, db_session: Session, planning_service: PlanningService
    ) -> None:
        forecastable = Product(sku="SKU-1", name="A", category="Cat")
        too_new = Product(sku="SKU-2", name="B", category="Cat")
        db_session.add_all([forecastable, too_new])
        db_session.commit()
        _add_history(db_session, forecastable, [100, 110, 120, 130])
        _add_history(db_session, too_new, [10])  # below min_history_periods=3

        run = planning_service.run_forecast(horizon=1)

        assert run.products_forecasted == 1
        assert run.products_skipped == 1
        assert run.notes["skipped"][0]["sku"] == "SKU-2"

    def test_excludes_inactive_products_by_default(
        self, db_session: Session, planning_service: PlanningService
    ) -> None:
        active = Product(sku="SKU-1", name="A", category="Cat", active=True)
        inactive = Product(sku="SKU-2", name="B", category="Cat", active=False)
        db_session.add_all([active, inactive])
        db_session.commit()
        _add_history(db_session, active, [100, 110, 120])
        _add_history(db_session, inactive, [50, 55, 60])

        run = planning_service.run_forecast(horizon=1)

        assert run.products_forecasted == 1

    def test_raises_not_found_when_no_products_match(
        self, db_session: Session, planning_service: PlanningService
    ) -> None:
        with pytest.raises(NotFoundError):
            planning_service.run_forecast(horizon=1, product_ids=[9999])

    def test_persists_forecast_generates_open_exceptions(
        self, db_session: Session, planning_service: PlanningService
    ) -> None:
        product = Product(sku="SKU-1", name="A", category="Cat", lead_time_days=14)
        db_session.add(product)
        db_session.commit()
        _add_history(db_session, product, [100, 100, 100, 100])
        db_session.add(
            InventorySnapshot(
                product_id=product.id, snapshot_date=date(2025, 4, 1), on_hand_units=5, on_order_units=0
            )
        )
        db_session.commit()

        planning_service.run_forecast(horizon=2)

        exceptions = (
            db_session.execute(
                select(PlanningException).where(PlanningException.product_id == product.id)
            )
            .scalars()
            .all()
        )
        assert any(item.exception_type == "stockout_risk" for item in exceptions)
        assert all(item.status == ExceptionStatus.OPEN.value for item in exceptions)


class TestForecastProduct:
    def test_adhoc_preview_does_not_persist_by_default(
        self, db_session: Session, planning_service: PlanningService
    ) -> None:
        product = Product(sku="SKU-1", name="A", category="Cat")
        db_session.add(product)
        db_session.commit()
        _add_history(db_session, product, [10, 12, 14, 16])

        planning_service.forecast_product(product.id, horizon=1, persist=False)

        assert db_session.execute(select(Forecast)).scalars().all() == []

    def test_adhoc_forecast_with_persist_true_writes_a_run(
        self, db_session: Session, planning_service: PlanningService
    ) -> None:
        product = Product(sku="SKU-1", name="A", category="Cat")
        db_session.add(product)
        db_session.commit()
        _add_history(db_session, product, [10, 12, 14, 16])

        _, result = planning_service.forecast_product(product.id, horizon=1, persist=True)

        assert result.points
        stored = db_session.execute(select(Forecast).where(Forecast.product_id == product.id)).scalars().all()
        assert len(stored) == 1

    def test_unknown_product_raises_not_found(
        self, db_session: Session, planning_service: PlanningService
    ) -> None:
        with pytest.raises(NotFoundError):
            planning_service.forecast_product(9999, horizon=1)


class TestExceptionLifecycle:
    def test_refresh_replaces_prior_open_exceptions(
        self, db_session: Session, planning_service: PlanningService
    ) -> None:
        product = Product(sku="SKU-1", name="A", category="Cat")
        db_session.add(product)
        db_session.commit()
        _add_history(db_session, product, [100, 100, 100, 500])  # spike on last period

        planning_service.run_forecast(horizon=1)
        first_pass = (
            db_session.execute(select(PlanningException).where(PlanningException.product_id == product.id))
            .scalars()
            .all()
        )
        assert len(first_pass) >= 1

        # Re-running should not duplicate the same open exception.
        planning_service.run_forecast(horizon=1)
        second_pass = (
            db_session.execute(select(PlanningException).where(PlanningException.product_id == product.id))
            .scalars()
            .all()
        )
        assert len(second_pass) == len(first_pass)

    def test_acknowledging_exception_survives_a_rerun(
        self, db_session: Session, planning_service: PlanningService
    ) -> None:
        product = Product(sku="SKU-1", name="A", category="Cat")
        db_session.add(product)
        db_session.commit()
        _add_history(db_session, product, [100, 100, 100, 500])

        planning_service.run_forecast(horizon=1)
        exception = db_session.execute(select(PlanningException)).scalars().first()
        planning_service.update_exception_status(exception.id, ExceptionStatus.ACKNOWLEDGED.value)

        # Re-run must not delete or reopen the acknowledged exception.
        planning_service.run_forecast(horizon=1)
        refreshed = db_session.get(PlanningException, exception.id)
        assert refreshed is not None
        assert refreshed.status == ExceptionStatus.ACKNOWLEDGED.value

    def test_update_status_unknown_id_raises(
        self, db_session: Session, planning_service: PlanningService
    ) -> None:
        with pytest.raises(NotFoundError):
            planning_service.update_exception_status(9999, ExceptionStatus.RESOLVED.value)


class TestInsights:
    def test_product_insight_uses_template_fallback_when_ai_disabled(
        self, db_session: Session, planning_service: PlanningService
    ) -> None:
        product = Product(sku="SKU-1", name="Widget", category="Cat")
        db_session.add(product)
        db_session.commit()
        _add_history(db_session, product, [100, 110, 120, 130])
        planning_service.run_forecast(horizon=2)

        insight = planning_service.generate_product_insight(product.id)

        assert insight.generated_by == "template"
        assert "Widget" in insight.headline or "Widget" in insight.summary

    def test_portfolio_insight_reflects_open_exceptions(
        self, db_session: Session, planning_service: PlanningService
    ) -> None:
        product = Product(sku="SKU-1", name="Widget", category="Cat", lead_time_days=14)
        db_session.add(product)
        db_session.commit()
        _add_history(db_session, product, [100, 100, 100, 100])
        db_session.add(
            InventorySnapshot(
                product_id=product.id, snapshot_date=date(2025, 4, 1), on_hand_units=1, on_order_units=0
            )
        )
        db_session.commit()
        planning_service.run_forecast(horizon=2)

        insight = planning_service.generate_portfolio_insight()

        assert insight.scope == "portfolio"
        assert insight.recommendations
