"""Validate immutable Meridian forecast-run artifacts and their business invariants."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from hashlib import sha256
from pathlib import Path
from typing import Any

import duckdb

ARTIFACT_FILENAMES = (
    "forecast_runs.parquet",
    "forecast_series_results.parquet",
    "forecast_model_evaluations.parquet",
    "forecasts.parquet",
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--forecast-root",
        required=True,
        type=Path,
        help="Directory containing one or more immutable forecast-run directories",
    )
    return parser


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as artifact_file:
        for chunk in iter(lambda: artifact_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _scalar(connection: duckdb.DuckDBPyConnection, query: str, parameters: list[Any]) -> Any:
    row = connection.execute(query, parameters).fetchone()
    if row is None:
        raise ValueError("Validation query unexpectedly returned no rows")
    return row[0]


def _validate_run(run_directory: Path) -> dict[str, Any]:
    manifest_path = run_directory / "forecast_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    run_id = str(manifest["run_id"])
    if run_directory.name != run_id:
        raise ValueError(f"Run directory name does not match manifest run_id: {run_directory}")

    for filename in ARTIFACT_FILENAMES:
        path = run_directory / filename
        if not path.is_file():
            raise ValueError(f"Forecast artifact is missing: {path}")
        expected_checksum = manifest["sha256"].get(filename)
        if expected_checksum != _file_sha256(path):
            raise ValueError(f"Forecast artifact checksum mismatch: {path}")

    run_path = str((run_directory / "forecast_runs.parquet").resolve())
    series_path = str((run_directory / "forecast_series_results.parquet").resolve())
    evaluations_path = str((run_directory / "forecast_model_evaluations.parquet").resolve())
    forecasts_path = str((run_directory / "forecasts.parquet").resolve())
    with duckdb.connect(":memory:") as connection:
        actual_counts = {
            "forecast_runs.parquet": int(
                _scalar(connection, "SELECT count(*) FROM read_parquet(?)", [run_path])
            ),
            "forecast_series_results.parquet": int(
                _scalar(connection, "SELECT count(*) FROM read_parquet(?)", [series_path])
            ),
            "forecast_model_evaluations.parquet": int(
                _scalar(connection, "SELECT count(*) FROM read_parquet(?)", [evaluations_path])
            ),
            "forecasts.parquet": int(
                _scalar(connection, "SELECT count(*) FROM read_parquet(?)", [forecasts_path])
            ),
        }
        if actual_counts != manifest["row_counts"]:
            raise ValueError(f"Manifest row counts do not match Parquet files for {run_id}")
        if actual_counts["forecast_runs.parquet"] != 1:
            raise ValueError(f"Forecast run {run_id} must contain exactly one run row")

        run_row = connection.execute(
            """
            SELECT run_id, data_version, status, horizon_months, interval_level,
                   series_count, successful_series_count, failed_series_count,
                   evaluation_count, forecast_count
            FROM read_parquet(?)
            """,
            [run_path],
        ).fetchone()
        if run_row is None:
            raise ValueError(f"Forecast run row is missing for {run_id}")
        (
            stored_run_id,
            data_version,
            status,
            horizon_months,
            interval_level,
            series_count,
            successful_count,
            failed_count,
            evaluation_count,
            forecast_count,
        ) = run_row
        if str(stored_run_id) != run_id or str(data_version) != str(manifest["data_version"]):
            raise ValueError(f"Forecast run identity mismatch for {run_id}")
        if int(horizon_months) != int(manifest["horizon_months"]):
            raise ValueError(f"Forecast horizon mismatch for {run_id}")
        if int(interval_level) != int(manifest["interval_level"]):
            raise ValueError(f"Forecast interval level mismatch for {run_id}")
        expected_run_counts = (
            actual_counts["forecast_series_results.parquet"],
            int(
                _scalar(
                    connection,
                    "SELECT count(*) FROM read_parquet(?) WHERE status = 'succeeded'",
                    [series_path],
                )
            ),
            int(
                _scalar(
                    connection,
                    "SELECT count(*) FROM read_parquet(?) WHERE status = 'failed'",
                    [series_path],
                )
            ),
            actual_counts["forecast_model_evaluations.parquet"],
            actual_counts["forecasts.parquet"],
        )
        if tuple(map(int, run_row[5:])) != expected_run_counts:
            raise ValueError(f"Forecast run summary counts are inconsistent for {run_id}")
        if int(series_count) != int(successful_count) + int(failed_count):
            raise ValueError(f"Forecast success/failure counts are inconsistent for {run_id}")
        expected_status = (
            "completed"
            if int(failed_count) == 0
            else "partial"
            if int(successful_count)
            else "failed"
        )
        if str(status) != expected_status:
            raise ValueError(f"Forecast run status is inconsistent for {run_id}")

        checks = {
            "duplicate_series": """
                SELECT count(*) - count(DISTINCT (store_id, product_id))
                FROM read_parquet(?)
            """,
            "duplicate_evaluations": """
                SELECT count(*) - count(DISTINCT (store_id, product_id, model_name))
                FROM read_parquet(?)
            """,
            "duplicate_forecasts": """
                SELECT count(*) - count(DISTINCT (store_id, product_id, period_start))
                FROM read_parquet(?)
            """,
        }
        for name, query in checks.items():
            query_path = series_path if name == "duplicate_series" else evaluations_path
            if name == "duplicate_forecasts":
                query_path = forecasts_path
            if int(_scalar(connection, query, [query_path])) != 0:
                raise ValueError(f"{name.replace('_', ' ')} found for {run_id}")

        invalid_forecasts = int(
            _scalar(
                connection,
                """
                SELECT count(*)
                FROM read_parquet(?)
                WHERE forecast_value < 0 OR lower_bound < 0 OR upper_bound < 0
                   OR lower_bound > forecast_value OR forecast_value > upper_bound
                   OR horizon NOT BETWEEN 1 AND ?
                """,
                [forecasts_path, int(horizon_months)],
            )
        )
        if invalid_forecasts:
            raise ValueError(f"Invalid forecast values or intervals found for {run_id}")

        invalid_series_forecast_counts = int(
            _scalar(
                connection,
                """
                SELECT count(*)
                FROM read_parquet(?) AS series
                LEFT JOIN (
                    SELECT store_id, product_id, count(*) AS points,
                           count(DISTINCT horizon) AS horizons
                    FROM read_parquet(?)
                    GROUP BY store_id, product_id
                ) AS forecast
                  ON forecast.store_id = series.store_id
                 AND forecast.product_id = series.product_id
                WHERE (series.status = 'succeeded' AND
                       (coalesce(forecast.points, 0) != ? OR
                        coalesce(forecast.horizons, 0) != ?))
                   OR (series.status = 'failed' AND coalesce(forecast.points, 0) != 0)
                """,
                [series_path, forecasts_path, int(horizon_months), int(horizon_months)],
            )
        )
        if invalid_series_forecast_counts:
            raise ValueError(f"Per-series forecast counts are inconsistent for {run_id}")

    return {
        "run_id": run_id,
        "data_version": str(data_version),
        "status": str(status),
        "series_count": int(series_count),
        "successful_series_count": int(successful_count),
        "failed_series_count": int(failed_count),
        "evaluation_count": int(evaluation_count),
        "forecast_count": int(forecast_count),
    }


def main(arguments: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(arguments)
    project_root = Path(__file__).resolve().parents[1]
    forecast_root = (
        args.forecast_root
        if args.forecast_root.is_absolute()
        else project_root / args.forecast_root
    )
    manifests = sorted(forecast_root.glob("*/forecast_manifest.json"))
    if not manifests:
        raise FileNotFoundError(f"No forecast runs found under: {forecast_root}")
    results = [_validate_run(manifest.parent) for manifest in manifests]
    print(json.dumps({"status": "valid", "runs": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
