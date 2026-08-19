"""Engine / session factory and the FastAPI request-scoped session dependency."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings


def _engine_kwargs(url: str) -> dict:
    """SQLite (used by the fast unit-test suite) rejects pool sizing options."""
    if url.startswith("sqlite"):
        kwargs: dict = {"connect_args": {"check_same_thread": False}}
        if ":memory:" in url:
            # Each pooled connection to an in-memory SQLite database is its own
            # separate, empty database. Pinning the pool to a single shared
            # connection is what makes ``sqlite:///:memory:`` usable across
            # multiple sessions/requests in the same process (e.g. the test suite).
            kwargs["poolclass"] = StaticPool
        return kwargs
    return {
        "pool_size": settings.db_pool_size,
        "max_overflow": settings.db_max_overflow,
        "pool_pre_ping": True,
    }


def build_engine(url: str | None = None) -> Engine:
    target = url or settings.database_url
    return create_engine(target, echo=settings.db_echo, future=True, **_engine_kwargs(target))


engine: Engine = build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    """Yield a session per request and always close it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
