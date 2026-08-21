"""Generate auditable forecast artifacts outside the public runtime."""

import json
import shutil
import tempfile
from datetime import date
from hashlib import sha256
from pathlib import Path

import pandas as pd

from app.application.forecasting import ForecastingEngine
from app.domain import Product
from app.domain.forecasting import ForecastMetrics
from app.forecast_runs.config import ForecastRunConfig
from app.ports.repositories.planning import PlanningReadRepository

ARTIFACT_FILENAMES = (
    "forecast_runs.parquet",
    "forecast_series_results.parquet",
    "forecast_model_evaluations.parquet",
    "forecasts.parquet",
)


class ForecastRunPublicationError(RuntimeError):
    """Raised when an immutable run cannot be published safely."""


def generate_forecast_run(
    config: ForecastRunConfig,
    project_root: Path,
    repository: PlanningReadRepository,
    engine: ForecastingEngine,
    *,
    overwrite: bool = False,
) -> Path:
    """Run all configured series and atomically publish a checksum-backed directory."""

    series_inputs: list[tuple[str, Product]] = []
    for store in repository.list_stores():
        for product in repository.search_products(store.store_id, "", limit=100_000):
            series_inputs.append((store.store_id, product))
    series_inputs.sort(key=lambda item: (item[0], item[1].sku))
    if config.maximum_series is not None:
        series_inputs = series_inputs[: config.maximum_series]
    if not series_inputs:
        raise ForecastRunPublicationError("No Store + SKU series are available for forecasting.")

    identity = json.dumps(
        {
            "data_version": config.data_version,
            "created_at": config.created_at.isoformat(),
            "horizon_months": config.horizon_months,
            "interval_level": config.interval_level,
            "series": [(store_id, product.product_id) for store_id, product in series_inputs],
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    run_id = f"forecast-{sha256(identity.encode()).hexdigest()[:16]}"
    output_root = config.resolved_output_root(project_root)
    output_directory = output_root / run_id
    if output_directory.exists() and not overwrite:
        raise ForecastRunPublicationError(
            f"Forecast run already exists: {output_directory}. Use --overwrite explicitly."
        )

    series_rows: list[dict[str, object]] = []
    evaluation_rows: list[dict[str, object]] = []
    forecast_rows: list[dict[str, object]] = []
    training_cutoffs: set[date] = set()

    for store_id, product in series_inputs:
        observations = repository.get_demand_series(store_id, product.product_id)
        if not observations:
            series_rows.append(
                _failed_series_row(
                    run_id, store_id, product, "No complete demand history is available."
                )
            )
            continue
        training_cutoff = observations[-1].period_start
        training_cutoffs.add(training_cutoff)
        try:
            result = engine.run(
                [observation.demand_units for observation in observations],
                training_cutoff=training_cutoff,
                horizon=config.horizon_months,
                interval_level=config.interval_level,
            )
            metrics = result.selected_metrics
            series_rows.append(
                {
                    "run_id": run_id,
                    "store_id": store_id,
                    "product_id": product.product_id,
                    "sku": product.sku,
                    "product_name": product.product_name,
                    "category": product.category,
                    "status": "succeeded",
                    "selected_model": result.selected_model,
                    **_metric_values(metrics),
                    "failure_detail": None,
                }
            )
            for evaluation in result.evaluations:
                evaluation_rows.append(
                    {
                        "run_id": run_id,
                        "store_id": store_id,
                        "product_id": product.product_id,
                        "sku": product.sku,
                        "model_name": evaluation.model_name,
                        "selected": evaluation.model_name == result.selected_model,
                        "status": evaluation.status,
                        "validation_origins": evaluation.validation_origins,
                        **_metric_values(evaluation.metrics),
                        "failure_detail": evaluation.failure_detail,
                    }
                )
            for point in result.forecasts:
                forecast_rows.append(
                    {
                        "run_id": run_id,
                        "store_id": store_id,
                        "product_id": product.product_id,
                        "sku": product.sku,
                        "period_start": point.period_start,
                        "forecast_value": point.forecast_value,
                        "lower_bound": point.lower_bound,
                        "upper_bound": point.upper_bound,
                        "horizon": point.horizon,
                        "selected_model": result.selected_model,
                        "training_cutoff": result.training_cutoff,
                    }
                )
        except Exception as error:
            series_rows.append(
                _failed_series_row(
                    run_id,
                    store_id,
                    product,
                    f"{type(error).__name__}: {error}",
                )
            )

    if len(training_cutoffs) != 1:
        raise ForecastRunPublicationError(
            "Every forecasted series must share one auditable training cutoff."
        )
    training_cutoff = training_cutoffs.pop()
    successful = sum(row["status"] == "succeeded" for row in series_rows)
    failed = len(series_rows) - successful
    run_status = "completed" if failed == 0 else "partial" if successful else "failed"
    run_rows = [
        {
            "run_id": run_id,
            "data_version": config.data_version,
            "status": run_status,
            "created_at": config.created_at,
            "training_cutoff": training_cutoff,
            "horizon_months": config.horizon_months,
            "interval_level": config.interval_level,
            "series_count": len(series_rows),
            "successful_series_count": successful,
            "failed_series_count": failed,
            "evaluation_count": len(evaluation_rows),
            "forecast_count": len(forecast_rows),
        }
    ]
    frames = {
        "forecast_runs.parquet": pd.DataFrame.from_records(run_rows),
        "forecast_series_results.parquet": pd.DataFrame.from_records(series_rows),
        "forecast_model_evaluations.parquet": pd.DataFrame.from_records(
            evaluation_rows, columns=_evaluation_columns()
        ),
        "forecasts.parquet": pd.DataFrame.from_records(forecast_rows, columns=_forecast_columns()),
    }
    _publish(output_root, output_directory, frames, config, run_id, overwrite=overwrite)
    return output_directory


def _metric_values(metrics: ForecastMetrics | None) -> dict[str, object]:
    if metrics is None:
        return {
            "wape": None,
            "mase": None,
            "rmse": None,
            "bias": None,
            "interval_coverage": None,
            "validation_points": None,
        }
    return {
        "wape": metrics.wape,
        "mase": metrics.mase,
        "rmse": metrics.rmse,
        "bias": metrics.bias,
        "interval_coverage": metrics.interval_coverage,
        "validation_points": metrics.validation_points,
    }


def _failed_series_row(
    run_id: str, store_id: str, product: Product, detail: str
) -> dict[str, object]:
    return {
        "run_id": run_id,
        "store_id": store_id,
        "product_id": product.product_id,
        "sku": product.sku,
        "product_name": product.product_name,
        "category": product.category,
        "status": "failed",
        "selected_model": None,
        **_metric_values(None),
        "failure_detail": detail,
    }


def _evaluation_columns() -> list[str]:
    return [
        "run_id",
        "store_id",
        "product_id",
        "sku",
        "model_name",
        "selected",
        "status",
        "validation_origins",
        "wape",
        "mase",
        "rmse",
        "bias",
        "interval_coverage",
        "validation_points",
        "failure_detail",
    ]


def _forecast_columns() -> list[str]:
    return [
        "run_id",
        "store_id",
        "product_id",
        "sku",
        "period_start",
        "forecast_value",
        "lower_bound",
        "upper_bound",
        "horizon",
        "selected_model",
        "training_cutoff",
    ]


def _publish(
    output_root: Path,
    output_directory: Path,
    frames: dict[str, pd.DataFrame],
    config: ForecastRunConfig,
    run_id: str,
    *,
    overwrite: bool,
) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{run_id}-", dir=output_root))
    try:
        for filename, frame in frames.items():
            frame.to_parquet(
                temporary / filename,
                compression=config.parquet_compression,
                index=False,
            )
        manifest = {
            "run_id": run_id,
            "data_version": config.data_version,
            "created_at": config.created_at.isoformat(),
            "horizon_months": config.horizon_months,
            "interval_level": config.interval_level,
            "row_counts": {name: len(frame) for name, frame in frames.items()},
            "sha256": {name: _file_sha256(temporary / name) for name in ARTIFACT_FILENAMES},
        }
        (temporary / "forecast_manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        if output_directory.exists():
            if not overwrite:
                raise ForecastRunPublicationError(
                    f"Forecast run already exists: {output_directory}"
                )
            shutil.rmtree(output_directory)
        temporary.rename(output_directory)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as artifact_file:
        for chunk in iter(lambda: artifact_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
