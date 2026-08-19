"""API integration tests for the product endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


class TestCreateProduct:
    def test_creates_and_returns_201(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/products",
            json={"sku": "sku-100", "name": "Widget", "category": "Gadgets"},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["sku"] == "SKU-100"  # normalised to upper-case
        assert body["id"] > 0

    def test_duplicate_sku_returns_409(self, client: TestClient) -> None:
        payload = {"sku": "SKU-DUP", "name": "Widget", "category": "Gadgets"}
        client.post("/api/v1/products", json=payload)
        response = client.post("/api/v1/products", json=payload)
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "conflict"

    def test_missing_required_field_returns_422(self, client: TestClient) -> None:
        response = client.post("/api/v1/products", json={"name": "No SKU"})
        assert response.status_code == 422


class TestListProducts:
    def test_returns_empty_page_initially(self, client: TestClient) -> None:
        response = client.get("/api/v1/products")
        assert response.status_code == 200
        body = response.json()
        assert body["items"] == []
        assert body["total"] == 0

    def test_filters_by_category(self, client: TestClient) -> None:
        client.post("/api/v1/products", json={"sku": "SKU-1", "name": "A", "category": "Beverages"})
        client.post("/api/v1/products", json={"sku": "SKU-2", "name": "B", "category": "Snacks"})

        response = client.get("/api/v1/products", params={"category": "Beverages"})
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["sku"] == "SKU-1"

    def test_search_matches_name_or_sku(self, client: TestClient) -> None:
        client.post("/api/v1/products", json={"sku": "SKU-1", "name": "Sparkling Water", "category": "Bev"})
        response = client.get("/api/v1/products", params={"search": "sparkling"})
        assert response.json()["total"] == 1

    def test_pagination_limit_and_offset(self, client: TestClient) -> None:
        for index in range(5):
            client.post(
                "/api/v1/products", json={"sku": f"SKU-{index}", "name": f"P{index}", "category": "Cat"}
            )
        response = client.get("/api/v1/products", params={"limit": 2, "offset": 2})
        body = response.json()
        assert len(body["items"]) == 2
        assert body["total"] == 5


class TestGetUpdateDeleteProduct:
    def test_get_unknown_product_returns_404(self, client: TestClient) -> None:
        response = client.get("/api/v1/products/9999")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"

    def test_update_changes_only_provided_fields(self, client: TestClient) -> None:
        created = client.post(
            "/api/v1/products", json={"sku": "SKU-1", "name": "Old Name", "category": "Cat"}
        ).json()

        response = client.patch(f"/api/v1/products/{created['id']}", json={"name": "New Name"})
        body = response.json()
        assert body["name"] == "New Name"
        assert body["category"] == "Cat"  # unchanged

    def test_delete_deactivates_rather_than_removes(self, client: TestClient) -> None:
        created = client.post(
            "/api/v1/products", json={"sku": "SKU-1", "name": "Widget", "category": "Cat"}
        ).json()

        delete_response = client.delete(f"/api/v1/products/{created['id']}")
        assert delete_response.status_code == 204

        get_response = client.get(f"/api/v1/products/{created['id']}")
        assert get_response.status_code == 200
        assert get_response.json()["active"] is False
