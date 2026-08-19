"""API integration tests for forecasting, exceptions, insights and analytics."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def _create_product(client: TestClient, sku: str = "SKU-1", lead_time_days: int = 14) -> dict:
    return client.post(
        "/api/v1/products",
        json={"sku": sku, "name": "Widget", "category": "Cat", "lead_time_days": lead_time_days},
    ).json()


def _post_history(client: TestClient, product_id: int, values: list[int], start_month: str = "2025-01") -> None:
    year, month = map(int, start_month.split("-"))
    records = []
    for value in values:
        records.append(
            {
                "product_id": product_id,
                "period_start": f"{year:04d}-{month:02d}-01",
                "units_sold": value,
            }
        )
        month += 1
        if month > 12:
            month = 1
            year += 1
    response = client.post("/api/v1/sales/bulk", json={"records": records})
    assert response.status_code == 200


class TestForecastRunEndpoint:
    def test_run_forecast_end_to_end(self, client: TestClient) -> None:
        product = _create_product(client)
        _post_history(client, product["id"], [100, 110, 120, 130])

        response = client.post("/api/v1/forecasts/runs", json={"horizon": 3, "model": "auto"})
        assert response.status_code == 201
        body = response.json()
        assert body["products_forecasted"] == 1
        assert body["products_skipped"] == 0

        lines = client.get(f"/api/v1/forecasts/runs/{body['id']}/lines").json()
        assert len(lines) == 3
        assert all(line["forecast_units"] >= 0 for line in lines)

    def test_run_with_no_products_returns_404(self, client: TestClient) -> None:
        response = client.post("/api/v1/forecasts/runs", json={"horizon": 3})
        assert response.status_code == 404

    def test_preview_does_not_persist(self, client: TestClient) -> None:
        product = _create_product(client)
        _post_history(client, product["id"], [10, 12, 14, 16])

        response = client.get(f"/api/v1/forecasts/preview/{product['id']}", params={"horizon": 2})
        assert response.status_code == 200
        body = response.json()
        assert len(body["points"]) == 2

        runs = client.get("/api/v1/forecasts/runs").json()
        assert runs == []

    def test_invalid_horizon_rejected(self, client: TestClient) -> None:
        response = client.post("/api/v1/forecasts/runs", json={"horizon": 0})
        assert response.status_code == 422


class TestExceptionEndpoints:
    def test_stockout_exception_appears_after_run(self, client: TestClient) -> None:
        product = _create_product(client, lead_time_days=14)
        _post_history(client, product["id"], [100, 100, 100, 100])
        client.post(
            "/api/v1/inventory",
            json={
                "product_id": product["id"],
                "snapshot_date": "2025-04-01",
                "on_hand_units": 5,
                "on_order_units": 0,
            },
        )

        client.post("/api/v1/forecasts/runs", json={"horizon": 2})

        response = client.get("/api/v1/exceptions", params={"status": "open"})
        assert response.status_code == 200
        types = [item["exception_type"] for item in response.json()]
        assert "stockout_risk" in types

    def test_update_status_transitions_exception(self, client: TestClient) -> None:
        product = _create_product(client)
        _post_history(client, product["id"], [100, 100, 100, 500])
        client.post("/api/v1/forecasts/runs", json={"horizon": 1})

        exceptions = client.get("/api/v1/exceptions").json()
        assert exceptions, "expected at least one exception to be generated"
        exception_id = exceptions[0]["id"]

        response = client.patch(f"/api/v1/exceptions/{exception_id}", json={"status": "resolved"})
        assert response.status_code == 200
        assert response.json()["status"] == "resolved"

        open_exceptions = client.get("/api/v1/exceptions", params={"status": "open"}).json()
        assert exception_id not in [item["id"] for item in open_exceptions]

    def test_update_unknown_exception_returns_404(self, client: TestClient) -> None:
        response = client.patch("/api/v1/exceptions/9999", json={"status": "resolved"})
        assert response.status_code == 404


class TestInsightEndpoint:
    def test_portfolio_insight_generation(self, client: TestClient) -> None:
        product = _create_product(client)
        _post_history(client, product["id"], [100, 110, 120, 130])
        client.post("/api/v1/forecasts/runs", json={"horizon": 2})

        response = client.post("/api/v1/insights", json={"scope": "portfolio"})
        assert response.status_code == 201
        body = response.json()
        assert body["generated_by"] == "template"  # AI_ENABLED=false in the test environment
        assert body["headline"]

    def test_product_scope_requires_product_id(self, client: TestClient) -> None:
        response = client.post("/api/v1/insights", json={"scope": "product"})
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"


class TestAnalyticsEndpoints:
    def test_summary_reflects_seeded_state(self, client: TestClient) -> None:
        product = _create_product(client)
        _post_history(client, product["id"], [100, 110, 120, 130])
        client.post("/api/v1/forecasts/runs", json={"horizon": 2})

        response = client.get("/api/v1/analytics/summary")
        body = response.json()
        assert body["active_products"] == 1
        assert body["forecast_total_units"] > 0

    def test_timeline_includes_history_and_forecast(self, client: TestClient) -> None:
        product = _create_product(client)
        _post_history(client, product["id"], [100, 110, 120, 130])
        client.post("/api/v1/forecasts/runs", json={"horizon": 2})

        response = client.get("/api/v1/analytics/timeline", params={"product_id": product["id"]})
        body = response.json()
        assert len(body["history"]) == 4
        assert len(body["forecast"]) == 2

    def test_product_detail_404_for_unknown_product(self, client: TestClient) -> None:
        response = client.get("/api/v1/analytics/products/9999")
        assert response.status_code == 404
