"""Command-line entry point: ``python -m app.seed.cli``.

Wipes and reseeds the configured database with deterministic demo data. Safe
to re-run — it truncates the planning tables first so it never duplicates.
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import delete

from app.core.logging import configure_logging, get_logger
from app.db.session import SessionLocal
from app.models import (
    Forecast,
    ForecastRun,
    Insight,
    InventorySnapshot,
    Location,
    PlanningException,
    Product,
    SalesHistory,
)
from app.seed.generator import DEFAULT_SEED, seed_database

logger = get_logger(__name__)


def _reset(db) -> None:
    """Delete in FK-safe order. Only ever used against dev/test databases."""
    for model in (
        Insight,
        PlanningException,
        Forecast,
        ForecastRun,
        InventorySnapshot,
        SalesHistory,
        Product,
        Location,
    ):
        db.execute(delete(model))
    db.commit()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed the demand planning database with demo data.")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Random seed (default: %(default)s)")
    parser.add_argument(
        "--no-reset", action="store_true", help="Skip truncating existing data before seeding"
    )
    args = parser.parse_args(argv)

    configure_logging()
    db = SessionLocal()
    try:
        if not args.no_reset:
            logger.info("clearing existing planning data")
            _reset(db)

        summary = seed_database(db, seed=args.seed)
        logger.info(
            "seed complete: %s locations, %s products, %s sales rows, %s inventory rows",
            summary.locations,
            summary.products,
            summary.sales_rows,
            summary.inventory_rows,
        )
        logger.info("engineered exception scenarios: %s", summary.scenarios)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
