"""Integration tests for the deterministic dummy-data generator."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.models import InventorySnapshot, Location, PlanningException, Product, SalesHistory
from app.seed.generator import DEFAULT_SEED, seed_database
from app.services.planning import PlanningService

pytestmark = pytest.mark.integration


class TestSeedGenerator:
    def test_creates_locations_products_and_history(self, db_session: Session) -> None:
        summary = seed_database(db_session)

        assert summary.locations == db_session.query(Location).count()
        assert summary.products == db_session.query(Product).count()
        assert db_session.query(SalesHistory).count() == summary.sales_rows
        assert db_session.query(InventorySnapshot).count() == summary.inventory_rows
        assert summary.products > 0
        assert summary.sales_rows > 0

    def test_same_seed_produces_identical_totals(self, db_session: Session) -> None:
        summary_a = seed_database(db_session, seed=123)
        total_a = sum(row.units_sold for row in db_session.query(SalesHistory).all())

        # Fresh session/engine, same seed.
        from sqlalchemy.orm import sessionmaker

        from app.db.base import Base
        from app.db.session import build_engine

        engine = build_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)()
        summary_b = seed_database(session, seed=123)
        total_b = sum(row.units_sold for row in session.query(SalesHistory).all())
        session.close()
        engine.dispose()

        assert summary_a.sales_rows == summary_b.sales_rows
        assert total_a == total_b

    def test_engineered_scenarios_are_present(self, db_session: Session) -> None:
        summary = seed_database(db_session)
        assert set(summary.scenarios) >= {
            _sku for _sku, scenario in summary.scenarios.items() if scenario
        }
        assert "demand_spike" in summary.scenarios.values()
        assert "demand_drop" in summary.scenarios.values()
        assert "new_product_volatility" in summary.scenarios.values()

    def test_seeded_data_is_forecastable_end_to_end(self, db_session: Session) -> None:
        """The generated dataset must survive a real forecast + exception cycle."""
        seed_database(db_session)
        service = PlanningService(db_session)

        run = service.run_forecast(horizon=3)

        assert run.products_forecasted > 0
        exceptions = db_session.query(PlanningException).all()
        # The engineered scenarios guarantee at least one exception fires.
        assert len(exceptions) > 0

    def test_default_seed_constant_is_stable(self) -> None:
        """Guards against an accidental change to the default seed breaking demos/docs."""
        assert DEFAULT_SEED == 20240601
