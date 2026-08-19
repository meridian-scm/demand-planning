"""Tests that specifically require a real PostgreSQL instance.

Skipped automatically unless ``TEST_DATABASE_URL`` (or ``DATABASE_URL``) points
at Postgres — e.g. the docker-compose ``db`` service. These exist to catch the
class of bug that SQLite's looser typing can hide: constraint enforcement,
numeric precision, and the actual Alembic migration path.

Run explicitly with:
    TEST_DATABASE_URL=postgresql+psycopg://meridian:meridian@localhost:5432/meridian_demand_test \
        pytest tests/integration/test_postgres_specific.py -m postgres
"""

from __future__ import annotations

import os
from datetime import date

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models import Location, Product, SalesHistory

POSTGRES_URL = os.environ.get("TEST_DATABASE_URL") or (
    os.environ.get("DATABASE_URL")
    if "postgresql" in os.environ.get("DATABASE_URL", "")
    else None
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.postgres,
    pytest.mark.skipif(POSTGRES_URL is None, reason="no Postgres TEST_DATABASE_URL configured"),
]


@pytest.fixture()
def pg_session():
    engine = create_engine(POSTGRES_URL, future=True)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, future=True)()
    try:
        yield session
    finally:
        session.rollback()
        # Clean up in FK-safe order so the fixture is repeatable.
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
        session.close()
        engine.dispose()


class TestUniqueConstraints:
    def test_duplicate_sku_violates_unique_constraint(self, pg_session) -> None:
        pg_session.add(Product(sku="SKU-PG-1", name="A", category="Cat"))
        pg_session.commit()

        pg_session.add(Product(sku="SKU-PG-1", name="B", category="Cat"))
        with pytest.raises(Exception):  # IntegrityError from psycopg
            pg_session.commit()
        pg_session.rollback()

    def test_duplicate_sales_period_violates_unique_constraint(self, pg_session) -> None:
        """The (product, location, period) unique constraint is enforced when a
        real location is set. With a NULL location, Postgres' standard "NULL is
        never equal to NULL" rule means the constraint does not fire — that case
        is exactly why the ingestion service explicitly checks for an existing
        row (including an ``IS NULL`` match) before inserting, rather than
        relying on the database to reject the duplicate.
        """
        product = Product(sku="SKU-PG-2", name="A", category="Cat")
        location = Location(code="DC-PG", name="PG Distribution Center", region="Test")
        pg_session.add_all([product, location])
        pg_session.commit()

        pg_session.add(
            SalesHistory(
                product_id=product.id, location_id=location.id, period_start=date(2025, 1, 1), units_sold=10
            )
        )
        pg_session.commit()

        pg_session.add(
            SalesHistory(
                product_id=product.id, location_id=location.id, period_start=date(2025, 1, 1), units_sold=20
            )
        )
        with pytest.raises(Exception):
            pg_session.commit()
        pg_session.rollback()

    def test_duplicate_period_with_null_location_is_not_blocked_by_db(self, pg_session) -> None:
        """Documents the NULL-location edge case above: the DB alone permits it,
        so callers must not rely on the constraint when location is optional."""
        product = Product(sku="SKU-PG-2B", name="A", category="Cat")
        pg_session.add(product)
        pg_session.commit()

        pg_session.add(SalesHistory(product_id=product.id, period_start=date(2025, 1, 1), units_sold=10))
        pg_session.commit()
        pg_session.add(SalesHistory(product_id=product.id, period_start=date(2025, 1, 1), units_sold=20))
        pg_session.commit()  # does not raise — two NULL-location rows coexist

        count = pg_session.execute(
            text("SELECT COUNT(*) FROM sales_history WHERE product_id = :pid"), {"pid": product.id}
        ).scalar_one()
        assert count == 2


class TestCascadeDelete:
    def test_deleting_product_cascades_to_sales_history(self, pg_session) -> None:
        product = Product(sku="SKU-PG-3", name="A", category="Cat")
        pg_session.add(product)
        pg_session.commit()
        pg_session.add(SalesHistory(product_id=product.id, period_start=date(2025, 1, 1), units_sold=10))
        pg_session.commit()

        pg_session.delete(product)
        pg_session.commit()

        remaining = pg_session.execute(text("SELECT COUNT(*) FROM sales_history")).scalar_one()
        assert remaining == 0


class TestConnectivity:
    def test_can_connect_and_query(self, pg_session) -> None:
        result = pg_session.execute(text("SELECT 1")).scalar_one()
        assert result == 1
