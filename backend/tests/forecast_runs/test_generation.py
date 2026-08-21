"""Tests for immutable forecast-run generation and DuckDB retrieval."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.application.forecasting import ForecastingEngine
from app.data_generation.artifacts import publish_artifacts
from app.data_generation.config import GeneratorConfig
from app.data_generation.generator import generate_artifacts
from app.forecast_runs.config import ForecastRunConfig
from app.forecast_runs.generation import ForecastRunPublicationError, generate_forecast_run
from app.infrastructure.duckdb import DuckDBForecastRunRepository, DuckDBPlanningRepository
from app.ports.forecasting import ModelPrediction


class _LastValueModel:
    name = "TestNaive"
    complexity_rank = 0

    def predict(
        self, history: tuple[float, ...], horizon: int, interval_level: int
    ) -> ModelPrediction:
        del interval_level
        value = history[-1]
        return ModelPrediction(
            mean=(value,) * horizon,
            lower=(max(0, value - 10),) * horizon,
            upper=(value + 10,) * horizon,
        )


def test_forecast_run_is_atomic_auditable_and_queryable(
    tmp_path: Path,
    generator_config: GeneratorConfig,
    project_root: Path,
) -> None:
    data_directory = tmp_path / "data" / "test-v1"
    data_config = generator_config.model_copy(update={"output_directory": data_directory})
    publish_artifacts(generate_artifacts(data_config), data_config, project_root)
    run_config = ForecastRunConfig(
        data_directory=data_directory,
        output_root=tmp_path / "forecast-runs",
        data_version="test-v1",
        created_at=datetime(2026, 1, 15, 12, tzinfo=UTC),
        horizon_months=6,
        interval_level=90,
        maximum_series=2,
    )
    planning_repository = DuckDBPlanningRepository(data_directory)
    engine = ForecastingEngine(lambda **_: (_LastValueModel(),))

    output = generate_forecast_run(
        run_config,
        project_root,
        planning_repository,
        engine,
    )

    assert (output / "forecast_manifest.json").is_file()
    repository = DuckDBForecastRunRepository(run_config.output_root)
    runs = repository.list_runs()
    assert len(runs) == 1
    assert runs[0].status == "completed"
    assert runs[0].series_count == 2
    assert runs[0].successful_series_count == 2
    assert runs[0].forecast_count == 12

    series = repository.list_series(runs[0].run_id, store_id=None, query="", limit=10)
    assert len(series) == 2
    assert all(item.selected_model == "TestNaive" for item in series)
    evaluations = repository.get_evaluations(
        runs[0].run_id, series[0].store_id, series[0].product_id
    )
    forecasts = repository.get_forecasts(runs[0].run_id, series[0].store_id, series[0].product_id)
    assert len(evaluations) == 1
    assert evaluations[0].selected
    assert len(forecasts) == 6
    assert all(
        point.lower_bound <= point.forecast_value <= point.upper_bound for point in forecasts
    )
    assert repository.get_run("../unsafe") is None

    (output / "forecast_manifest.json").write_text("{}", encoding="utf-8")
    untrusted_repository = DuckDBForecastRunRepository(run_config.output_root)
    assert untrusted_repository.get_run(runs[0].run_id) is None
    assert untrusted_repository.list_runs() == ()

    with pytest.raises(ForecastRunPublicationError, match="already exists"):
        generate_forecast_run(
            run_config,
            project_root,
            planning_repository,
            engine,
        )
