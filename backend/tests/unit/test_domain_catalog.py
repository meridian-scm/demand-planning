"""Tests for framework-independent catalog entities."""

from decimal import Decimal

import pytest
from app.domain import Product, Store, StoreProduct


def test_catalog_entities_accept_valid_planning_data() -> None:
    store = Store(
        "store-1", "TOR-01", "Toronto Central", "Toronto", "Ontario", "Canada", "America/Toronto"
    )
    product = Product(
        "product-1",
        "SKU-0001",
        "Whole Bean Coffee",
        "Grocery",
        "Coffee",
        "Northstar",
        Decimal("8.50"),
        Decimal("14.99"),
    )
    policy = StoreProduct("store-1", "product-1", "SKU-0001", True, 14, 30, 50)

    assert store.store_code == "TOR-01"
    assert product.sku == policy.sku
    assert policy.lead_time_days == 14


def test_store_product_rejects_negative_planning_values() -> None:
    with pytest.raises(ValueError, match="safety_stock must be nonnegative"):
        StoreProduct("store-1", "product-1", "SKU-0001", True, 14, -1, 50)
