"""Integration tests for immutable forecast-run API contracts."""

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.application.forecasting import ForecastingEngine
from app.config import Settings
from app.data_generation.artifacts import publish_artifacts
from app.data_generation.config import GeneratorConfig
from app.data_generation.generator import generate_artifacts
from app.forecast_runs.config import ForecastRunConfig
from app.forecast_runs.generation import generate_forecast_run
from app.infrastructure.duckdb import DuckDBForecastRunRepository, DuckDBPlanningRepository
from app.main import create_app
from app.ports.forecasting import ModelPrediction
from fastapi.testclient import TestClient


class _ApiTestModel:
    name = "ApiTestNaive"
    complexity_rank = 0

    def predict(
        self, history: tuple[float, ...], horizon: int, interval_level: int
    ) -> ModelPrediction:
        del interval_level
        value = history[-1]
        return ModelPrediction(
            mean=(value,) * horizon,
            lower=(max(0, value - 5),) * horizon,
            upper=(value + 5,) * horizon,
        )


@pytest.fixture
def forecast_run_client(
    tmp_path: Path,
    generator_config: GeneratorConfig,
    project_root: Path,
) -> Iterator[TestClient]:
    data_directory = tmp_path / "generated" / "test-v1"
    data_config = generator_config.model_copy(update={"output_directory": data_directory})
    publish_artifacts(generate_artifacts(data_config), data_config, project_root)
    planning_repository = DuckDBPlanningRepository(data_directory)
    run_config = ForecastRunConfig(
        data_directory=data_directory,
        output_root=data_directory / "forecast_runs",
        data_version="test-v1",
        created_at=datetime(2026, 1, 15, 12, tzinfo=UTC),
        maximum_series=2,
    )
    generate_forecast_run(
        run_config,
        project_root,
        planning_repository,
        ForecastingEngine(lambda **_: (_ApiTestModel(),)),
    )
    settings = Settings(
        environment="test",
        artifact_directory=data_directory.parent,
        artifact_data_version=data_directory.name,
    )
    with TestClient(
        create_app(
            settings,
            planning_repository,
            DuckDBForecastRunRepository(run_config.output_root),
        )
    ) as client:
        yield client


def test_forecast_run_endpoints_retrieve_auditable_artifacts(
    forecast_run_client: TestClient,
) -> None:
    runs_response = forecast_run_client.get("/api/v1/forecast-runs")
    assert runs_response.status_code == 200
    runs = runs_response.json()
    assert len(runs) == 1
    run = runs[0]
    assert run["status"] == "completed"
    assert run["series_count"] == 2
    assert run["successful_series_count"] == 2
    assert run["forecast_count"] == 12

    detail = forecast_run_client.get(f"/api/v1/forecast-runs/{run['run_id']}")
    assert detail.status_code == 200
    assert detail.json() == run

    series_response = forecast_run_client.get(
        f"/api/v1/forecast-runs/{run['run_id']}/series", params={"limit": 10}
    )
    assert series_response.status_code == 200
    series = series_response.json()
    assert len(series) == 2
    assert all(item["selected_model"] == "ApiTestNaive" for item in series)

    selection = series[0]
    identity = {
        "store_id": selection["store_id"],
        "product_id": selection["product_id"],
    }
    evaluations = forecast_run_client.get(
        f"/api/v1/forecast-runs/{run['run_id']}/evaluations", params=identity
    )
    forecasts = forecast_run_client.get(
        "/api/v1/forecasts", params={"run_id": run["run_id"], **identity}
    )
    assert evaluations.status_code == 200
    assert len(evaluations.json()) == 1
    assert evaluations.json()[0]["selected"]
    assert forecasts.status_code == 200
    assert len(forecasts.json()) == 6
    assert all(
        point["lower_bound"] <= point["forecast_value"] <= point["upper_bound"]
        for point in forecasts.json()
    )

    missing = forecast_run_client.get("/api/v1/forecast-runs/missing-run")
    unsafe = forecast_run_client.get("/api/v1/forecast-runs/..%2Funsafe")
    assert missing.status_code == 404
    assert unsafe.status_code in {404, 422}


def test_overview_endpoint_aggregates_the_published_run(
    forecast_run_client: TestClient,
) -> None:
    runs = forecast_run_client.get("/api/v1/forecast-runs").json()
    response = forecast_run_client.get(
        "/api/v1/dashboard/summary",
        params={"run_id": runs[0]["run_id"], "store_id": "store-001"},
    )

    assert response.status_code == 200
    overview = response.json()
    assert overview["run_id"] == runs[0]["run_id"]
    assert overview["store_id"] == "store-001"
    assert overview["series_count"] == 2
    assert overview["recent_12_month_demand"] > 0
    assert overview["prior_12_month_demand"] > 0
    assert overview["forecast_horizon_demand"] > 0
    assert len(overview["timeline"]) == 30
    assert sum(overview["risk_counts"].values()) == 2
    assert overview["median_series_wape"] is not None

    missing = forecast_run_client.get("/api/v1/dashboard/summary", params={"run_id": "missing-run"})
    assert missing.status_code == 404
