"""Read contracts for catalog data, independent of the storage adapter."""

from typing import Protocol

from app.domain import Product, Store, StoreProduct


class StoreRepository(Protocol):
    """Read stores without exposing infrastructure details."""

    def list_all(self) -> tuple[Store, ...]: ...

    def get(self, store_id: str) -> Store | None: ...


class ProductRepository(Protocol):
    """Read products without exposing infrastructure details."""

    def get(self, product_id: str) -> Product | None: ...

    def search(self, query: str, *, limit: int) -> tuple[Product, ...]: ...


class StoreProductRepository(Protocol):
    """Read Store + SKU planning policies."""

    def get(self, store_id: str, product_id: str) -> StoreProduct | None: ...
