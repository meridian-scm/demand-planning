"""Read planning data from immutable Parquet artifacts through DuckDB."""

from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import duckdb

from app.domain import DemandObservation, InventorySnapshot, Product, Store, StoreProduct


class DuckDBPlanningRepository:
    """A stateless, read-only analytical adapter over one artifact version."""

    _REQUIRED_FILES = (
        "manifest.json",
        "stores.parquet",
        "products.parquet",
        "store_products.parquet",
        "demand_history.parquet",
        "inventory_snapshots.parquet",
    )

    def __init__(self, artifact_directory: Path) -> None:
        self._artifact_directory = artifact_directory

    def _path(self, filename: str) -> str:
        return str((self._artifact_directory / filename).resolve())

    @staticmethod
    def _fetchall(sql: str, parameters: Sequence[object]) -> list[tuple[Any, ...]]:
        connection = duckdb.connect(database=":memory:")
        try:
            return connection.execute(sql, parameters).fetchall()
        finally:
            connection.close()

    def is_ready(self) -> bool:
        if any(not (self._artifact_directory / name).is_file() for name in self._REQUIRED_FILES):
            return False
        try:
            rows = self._fetchall(
                "SELECT count(*) FROM read_parquet(?)",
                [self._path("demand_history.parquet")],
            )
            return bool(rows and int(rows[0][0]) > 0)
        except duckdb.Error:
            return False

    def list_stores(self) -> tuple[Store, ...]:
        rows = self._fetchall(
            """
            SELECT store_id, store_code, store_name, city, region, country, timezone
            FROM read_parquet(?)
            ORDER BY store_name
            """,
            [self._path("stores.parquet")],
        )
        return tuple(Store(*map(str, row)) for row in rows)

    def search_products(self, store_id: str, query: str, *, limit: int) -> tuple[Product, ...]:
        rows = self._fetchall(
            """
            SELECT p.product_id, p.sku, p.product_name, p.category, p.subcategory,
                   p.brand, p.unit_cost, p.unit_price
            FROM read_parquet(?) AS p
            INNER JOIN read_parquet(?) AS sp
                ON sp.product_id = p.product_id AND sp.sku = p.sku
            WHERE sp.store_id = ? AND sp.active
              AND (
                  ? = ''
                  OR contains(lower(p.sku), lower(?))
                  OR contains(lower(p.product_name), lower(?))
                  OR contains(lower(p.category), lower(?))
              )
            ORDER BY p.sku
            LIMIT ?
            """,
            [
                self._path("products.parquet"),
                self._path("store_products.parquet"),
                store_id,
                query,
                query,
                query,
                query,
                limit,
            ],
        )
        return tuple(
            Product(
                product_id=str(row[0]),
                sku=str(row[1]),
                product_name=str(row[2]),
                category=str(row[3]),
                subcategory=str(row[4]),
                brand=str(row[5]),
                unit_cost=Decimal(row[6]),
                unit_price=Decimal(row[7]),
            )
            for row in rows
        )

    def get_product(self, product_id: str) -> Product | None:
        rows = self._fetchall(
            """
            SELECT product_id, sku, product_name, category, subcategory, brand,
                   unit_cost, unit_price
            FROM read_parquet(?) WHERE product_id = ? LIMIT 1
            """,
            [self._path("products.parquet"), product_id],
        )
        if not rows:
            return None
        row = rows[0]
        return Product(
            product_id=str(row[0]),
            sku=str(row[1]),
            product_name=str(row[2]),
            category=str(row[3]),
            subcategory=str(row[4]),
            brand=str(row[5]),
            unit_cost=Decimal(row[6]),
            unit_price=Decimal(row[7]),
        )

    def get_store_product(self, store_id: str, product_id: str) -> StoreProduct | None:
        rows = self._fetchall(
            """
            SELECT store_id, product_id, sku, active, lead_time_days, safety_stock,
                   reorder_point, minimum_order_quantity, order_multiple, service_level_target
            FROM read_parquet(?)
            WHERE store_id = ? AND product_id = ? LIMIT 1
            """,
            [self._path("store_products.parquet"), store_id, product_id],
        )
        if not rows:
            return None
        row = rows[0]
        return StoreProduct(
            store_id=str(row[0]),
            product_id=str(row[1]),
            sku=str(row[2]),
            active=bool(row[3]),
            lead_time_days=int(row[4]),
            safety_stock=int(row[5]),
            reorder_point=int(row[6]),
            minimum_order_quantity=int(row[7]),
            order_multiple=int(row[8]),
            service_level_target=float(row[9]),
        )

    def get_demand_series(self, store_id: str, product_id: str) -> tuple[DemandObservation, ...]:
        rows = self._fetchall(
            """
            SELECT store_id, product_id, sku, period_start, demand_units
            FROM read_parquet(?)
            WHERE store_id = ? AND product_id = ?
            ORDER BY period_start
            """,
            [self._path("demand_history.parquet"), store_id, product_id],
        )
        return tuple(
            DemandObservation(
                store_id=str(row[0]),
                product_id=str(row[1]),
                sku=str(row[2]),
                period_start=cast(date, row[3]),
                demand_units=int(row[4]),
            )
            for row in rows
        )

    def get_inventory_snapshot(self, store_id: str, product_id: str) -> InventorySnapshot | None:
        rows = self._fetchall(
            """
            SELECT store_id, product_id, sku, snapshot_at, on_hand, allocated, on_order,
                   on_order_due_within_lead_time, next_expected_receipt_at,
                   lead_time_days, safety_stock
            FROM read_parquet(?)
            WHERE store_id = ? AND product_id = ?
            ORDER BY snapshot_at DESC
            LIMIT 1
            """,
            [self._path("inventory_snapshots.parquet"), store_id, product_id],
        )
        if not rows:
            return None
        row = rows[0]
        return InventorySnapshot(
            store_id=str(row[0]),
            product_id=str(row[1]),
            sku=str(row[2]),
            snapshot_at=cast(datetime, row[3]),
            on_hand=int(row[4]),
            allocated=int(row[5]),
            on_order=int(row[6]),
            on_order_due_within_lead_time=int(row[7]),
            next_expected_receipt_at=(cast(datetime, row[8]) if row[8] is not None else None),
            lead_time_days=int(row[9]),
            safety_stock=int(row[10]),
        )
