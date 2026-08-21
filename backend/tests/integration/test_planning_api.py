"""Integration tests for planner-facing API contracts."""

import pytest
from fastapi.testclient import TestClient


def test_planner_can_select_catalog_and_load_demand_series(
    published_client: TestClient,
) -> None:
    stores_response = published_client.get("/api/v1/stores")
    assert stores_response.status_code == 200
    stores = stores_response.json()
    assert len(stores) == 5

    products_response = published_client.get(
        "/api/v1/products", params={"store_id": stores[0]["store_id"], "limit": 5}
    )
    assert products_response.status_code == 200
    products = products_response.json()
    assert len(products) == 5

    demand_response = published_client.get(
        "/api/v1/demand/series",
        params={
            "store_id": stores[0]["store_id"],
            "product_id": products[0]["product_id"],
        },
    )
    assert demand_response.status_code == 200
    payload = demand_response.json()
    assert payload["product"]["sku"] == products[0]["sku"]
    assert len(payload["observations"]) == 60
    assert payload["summary"]["total_units"] > 0


def test_unknown_store_product_series_returns_404(published_client: TestClient) -> None:
    response = published_client.get(
        "/api/v1/demand/series",
        params={"store_id": "missing-store", "product_id": "missing-product"},
    )

    assert response.status_code == 404


def test_demand_signals_expose_rules_and_structured_evidence(
    published_client: TestClient,
) -> None:
    response = published_client.get(
        "/api/v1/signals",
        params={"store_id": "store-001", "product_id": "product-00001"},
    )

    assert response.status_code == 200
    signals = response.json()
    trend = next(signal for signal in signals if signal["signal_type"] == "trend")
    assert trend["direction"] in {"growing", "declining", "stable"}
    assert trend["metric_name"] == "recent_vs_prior_year_change"
    assert "recent_12_month_average" in trend["evidence"]
    assert "prior_12_month_average" in trend["evidence"]
    assert trend["signal_id"].startswith("signal-")


def test_unknown_series_signals_return_404(published_client: TestClient) -> None:
    response = published_client.get(
        "/api/v1/signals",
        params={"store_id": "missing-store", "product_id": "missing-product"},
    )

    assert response.status_code == 404


def test_inventory_position_and_lead_time_risk_expose_planner_evidence(
    published_client: TestClient,
) -> None:
    parameters = {"store_id": "store-001", "product_id": "product-00001"}

    position_response = published_client.get("/api/v1/inventory/positions", params=parameters)
    risk_response = published_client.get("/api/v1/inventory/risks", params=parameters)

    assert position_response.status_code == 200
    position = position_response.json()
    assert position["sku"] == "SKU-00001"
    assert position["on_order_due_within_lead_time"] <= position["on_order"]
    assert position["snapshot_at"].endswith(("Z", "+00:00", "-05:00", "-04:00"))

    assert risk_response.status_code == 200
    risk = risk_response.json()
    assert risk["classification"] in {
        "stockout",
        "below_safety_stock",
        "healthy",
        "excess",
    }
    assert risk["risk_id"].startswith("risk-")
    assert risk["forecast_demand_during_lead_time"] >= 0
    assert risk["projected_inventory"] == pytest.approx(
        risk["available_inventory"]
        + risk["on_order_due_within_lead_time"]
        - risk["forecast_demand_during_lead_time"]
    )
    assert risk["selected_model"]
    assert risk["forecast_id"].startswith("preview-")


def test_unknown_inventory_position_and_risk_return_404(
    published_client: TestClient,
) -> None:
    parameters = {"store_id": "missing-store", "product_id": "missing-product"}

    assert published_client.get("/api/v1/inventory/positions", params=parameters).status_code == 404
    assert published_client.get("/api/v1/inventory/risks", params=parameters).status_code == 404


def test_planning_exceptions_are_prioritized_filterable_and_traceable(
    published_client: TestClient,
) -> None:
    parameters = {"store_id": "store-001", "product_id": "product-00001"}

    response = published_client.get("/api/v1/exceptions", params=parameters)

    assert response.status_code == 200
    exceptions = response.json()
    assert exceptions
    assert [item["priority_score"] for item in exceptions] == sorted(
        (item["priority_score"] for item in exceptions), reverse=True
    )
    assert all(item["status"] == "open" for item in exceptions)
    assert all(item["exception_id"].startswith("exception-") for item in exceptions)
    assert any(
        item["related_risk_id"] or item["related_signal_id"] or item["related_forecast_id"]
        for item in exceptions
    )

    severity = exceptions[0]["severity"]
    filtered = published_client.get(
        "/api/v1/exceptions", params={**parameters, "severity": severity}
    )
    assert filtered.status_code == 200
    assert filtered.json()
    assert all(item["severity"] == severity for item in filtered.json())


def test_exception_api_validates_filters_and_unknown_series(
    published_client: TestClient,
) -> None:
    invalid = published_client.get(
        "/api/v1/exceptions",
        params={
            "store_id": "store-001",
            "product_id": "product-00001",
            "severity": "urgent",
        },
    )
    missing = published_client.get(
        "/api/v1/exceptions",
        params={"store_id": "missing-store", "product_id": "missing-product"},
    )

    assert invalid.status_code == 422
    assert missing.status_code == 404


def test_stateless_forecast_preview_returns_selection_metrics_and_intervals(
    published_client: TestClient,
) -> None:
    response = published_client.post(
        "/api/v1/forecast-previews",
        json={
            "store_id": "store-001",
            "product_id": "product-00001",
            "horizon_months": 6,
            "interval_level": 90,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["forecast_id"].startswith("preview-")
    assert payload["selected_model"] in {
        "Naive",
        "SeasonalNaive",
        "RandomWalkWithDrift",
        "AutoETS",
        "AutoTheta",
        "CrostonOptimized",
    }
    assert payload["validation_origins"] == 4
    assert payload["selected_metrics"]["validation_points"] == 24
    assert len(payload["forecasts"]) == 6
    assert all(point["lower_bound"] >= 0 for point in payload["forecasts"])
    assert all(
        point["lower_bound"] <= point["forecast_value"] <= point["upper_bound"]
        for point in payload["forecasts"]
    )
    assert len(payload["evaluations"]) >= 3


def test_forecast_preview_validates_horizon(published_client: TestClient) -> None:
    response = published_client.post(
        "/api/v1/forecast-previews",
        json={
            "store_id": "store-001",
            "product_id": "product-00001",
            "horizon_months": 13,
        },
    )

    assert response.status_code == 422
