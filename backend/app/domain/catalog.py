"""Minimal catalog entities for the Store + SKU planning grain."""

from dataclasses import dataclass
from decimal import Decimal


def _require_text(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")


@dataclass(frozen=True, slots=True)
class Store:
    """A physical demand-planning location."""

    store_id: str
    store_code: str
    store_name: str
    city: str
    region: str
    country: str
    timezone: str

    def __post_init__(self) -> None:
        for field_name in (
            "store_id",
            "store_code",
            "store_name",
            "city",
            "region",
            "country",
            "timezone",
        ):
            _require_text(getattr(self, field_name), field_name)


@dataclass(frozen=True, slots=True)
class Product:
    """A globally identified product with one unique SKU."""

    product_id: str
    sku: str
    product_name: str
    category: str
    subcategory: str
    brand: str
    unit_cost: Decimal
    unit_price: Decimal

    def __post_init__(self) -> None:
        for field_name in (
            "product_id",
            "sku",
            "product_name",
            "category",
            "subcategory",
            "brand",
        ):
            _require_text(getattr(self, field_name), field_name)
        if self.unit_cost < 0:
            raise ValueError("unit_cost must be nonnegative")
        if self.unit_price < 0:
            raise ValueError("unit_price must be nonnegative")


@dataclass(frozen=True, slots=True)
class StoreProduct:
    """Store-specific planning policy for a product."""

    store_id: str
    product_id: str
    sku: str
    active: bool
    lead_time_days: int
    safety_stock: int
    reorder_point: int

    def __post_init__(self) -> None:
        _require_text(self.store_id, "store_id")
        _require_text(self.product_id, "product_id")
        _require_text(self.sku, "sku")
        if self.lead_time_days < 0:
            raise ValueError("lead_time_days must be nonnegative")
        if self.safety_stock < 0:
            raise ValueError("safety_stock must be nonnegative")
        if self.reorder_point < 0:
            raise ValueError("reorder_point must be nonnegative")
