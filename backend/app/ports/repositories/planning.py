"""Read contract for the planner-facing analytical data."""

from typing import Protocol

from app.domain import DemandObservation, InventorySnapshot, Product, Store, StoreProduct


class PlanningReadRepository(Protocol):
    """Read planning data without exposing DuckDB or Parquet details."""

    def is_ready(self) -> bool: ...

    def list_stores(self) -> tuple[Store, ...]: ...

    def search_products(self, store_id: str, query: str, *, limit: int) -> tuple[Product, ...]: ...

    def get_store_product(self, store_id: str, product_id: str) -> StoreProduct | None: ...

    def get_product(self, product_id: str) -> Product | None: ...

    def get_demand_series(
        self, store_id: str, product_id: str
    ) -> tuple[DemandObservation, ...]: ...

    def get_inventory_snapshot(
        self, store_id: str, product_id: str
    ) -> InventorySnapshot | None: ...
