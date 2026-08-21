"""Command-line entry point for immutable offline forecast runs."""

import argparse
from pathlib import Path

from app.application.forecasting import ForecastingEngine
from app.forecast_runs.config import load_forecast_run_config
from app.forecast_runs.generation import generate_forecast_run
from app.infrastructure.duckdb import DuckDBPlanningRepository
from app.infrastructure.forecasting import build_candidate_models


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    parsed = parser.parse_args(arguments)

    project_root = Path(__file__).resolve().parents[3]
    config_path = parsed.config if parsed.config.is_absolute() else project_root / parsed.config
    config = load_forecast_run_config(config_path)
    repository = DuckDBPlanningRepository(config.resolved_data_directory(project_root))
    output = generate_forecast_run(
        config,
        project_root,
        repository,
        ForecastingEngine(build_candidate_models),
        overwrite=parsed.overwrite,
    )
    print(f"Published forecast run: {output}")
    return 0
