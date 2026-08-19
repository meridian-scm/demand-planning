"""Shared pytest fixtures.

The suite runs against an in-memory SQLite database by default so it needs no
external services and stays fast (`pytest -m unit` runs in well under a
second). SQLite is schema-compatible with the ORM models used here — none of
them rely on Postgres-only types — so this is a faithful stand-in for unit and
integration coverage. The seed generator, migrations, and a small marked
subset of tests are additionally exercised against real Postgres in CI and in
``tests/integration/test_postgres_specific.py``.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("AI_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from app.db.base import Base  # noqa: E402
from app.db.session import build_engine, get_db  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import Location, Product  # noqa: E402


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(connection, _) -> None:  # pragma: no cover - driver hook
    """SQLite ignores FK constraints unless explicitly told not to."""
    if type(connection).__module__.startswith("sqlite3"):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    """A fresh, isolated in-memory database for a single test."""
    engine = build_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """A FastAPI TestClient wired to the isolated in-memory database."""
    app = create_app()

    def _override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def sample_location(db_session: Session) -> Location:
    location = Location(code="DC-TEST", name="Test Distribution Center", region="Test Region")
    db_session.add(location)
    db_session.commit()
    db_session.refresh(location)
    return location


@pytest.fixture()
def sample_product(db_session: Session) -> Product:
    product = Product(
        sku="SKU-TEST-1",
        name="Test Widget",
        category="Test Category",
        unit_cost=5.0,
        unit_price=10.0,
        lead_time_days=30,
        safety_stock_units=10,
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)
    return product


def months_back(anchor: date, count: int) -> list[date]:
    """Helper: the ``count`` months up to and including ``anchor``'s month, ascending."""
    from app.services.forecasting.engine import add_months, normalise_period

    start = normalise_period(anchor)
    return [add_months(start, offset - count + 1) for offset in range(count)]
