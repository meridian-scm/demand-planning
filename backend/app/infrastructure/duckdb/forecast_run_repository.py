"""DuckDB reads over checksum-verified, immutable forecast-run artifacts."""

import json
import re
from collections.abc import Sequence
from datetime import date, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

import duckdb

from app.domain import ForecastRun, ForecastSeriesResult, StoredForecast, StoredModelEvaluation
from app.domain.forecast_runs import EvaluationStatus, RunStatus, SeriesRunStatus

_SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9._-]+$")
_ARTIFACT_FILENAMES = (
    "forecast_runs.parquet",
    "forecast_series_results.parquet",
    "forecast_model_evaluations.parquet",
    "forecasts.parquet",
)


class DuckDBForecastRunRepository:
    """Read complete forecast-run directories without exposing storage details."""

    def __init__(self, root_directory: Path) -> None:
        self._root_directory = root_directory
        self._validated_run_ids: set[str] = set()

    @staticmethod
    def _fetchall(sql: str, parameters: Sequence[object]) -> list[tuple[Any, ...]]:
        connection = duckdb.connect(database=":memory:")
        try:
            return connection.execute(sql, parameters).fetchall()
        finally:
            connection.close()

    def _artifact_path(self, run_id: str, filename: str) -> Path | None:
        if not self._validate_run(run_id):
            return None
        path = self._root_directory / run_id / filename
        return path if path.is_file() else None

    def _validate_run(self, run_id: str) -> bool:
        """Accept a published run only when its identity and checksums are intact."""

        if not _SAFE_RUN_ID.fullmatch(run_id):
            return False
        if run_id in self._validated_run_ids:
            return True
        run_directory = self._root_directory / run_id
        manifest_path = run_directory / "forecast_manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            checksums = manifest["sha256"]
            if manifest["run_id"] != run_id:
                return False
            for filename in _ARTIFACT_FILENAMES:
                artifact = run_directory / filename
                if not artifact.is_file() or checksums.get(filename) != _file_sha256(artifact):
                    return False
        except (OSError, json.JSONDecodeError, KeyError, TypeError):
            return False
        self._validated_run_ids.add(run_id)
        return True

    def list_runs(self) -> tuple[ForecastRun, ...]:
        runs = [
            run
            for path in sorted(self._root_directory.glob("*/forecast_runs.parquet"))
            if self._validate_run(path.parent.name) and (run := self._read_run(path)) is not None
        ]
        return tuple(sorted(runs, key=lambda run: (run.created_at, run.run_id), reverse=True))

    def get_run(self, run_id: str) -> ForecastRun | None:
        path = self._artifact_path(run_id, "forecast_runs.parquet")
        return self._read_run(path) if path is not None else None

    def _read_run(self, path: Path) -> ForecastRun | None:
        try:
            rows = self._fetchall(
                """
                SELECT run_id, data_version, status, created_at, training_cutoff,
                       horizon_months, interval_level, series_count,
                       successful_series_count, failed_series_count, evaluation_count,
                       forecast_count
                FROM read_parquet(?) LIMIT 1
                """,
                [str(path.resolve())],
            )
        except duckdb.Error:
            return None
        if not rows:
            return None
        row = rows[0]
        return ForecastRun(
            run_id=str(row[0]),
            data_version=str(row[1]),
            status=cast(RunStatus, str(row[2])),
            created_at=cast(datetime, row[3]),
            training_cutoff=cast(date, row[4]),
            horizon_months=int(row[5]),
            interval_level=int(row[6]),
            series_count=int(row[7]),
            successful_series_count=int(row[8]),
            failed_series_count=int(row[9]),
            evaluation_count=int(row[10]),
            forecast_count=int(row[11]),
        )

    def list_series(
        self,
        run_id: str,
        *,
        store_id: str | None,
        query: str,
        limit: int,
    ) -> tuple[ForecastSeriesResult, ...]:
        path = self._artifact_path(run_id, "forecast_series_results.parquet")
        if path is None:
            return ()
        rows = self._fetchall(
            """
            SELECT run_id, store_id, product_id, sku, product_name, category, status,
                   selected_model, wape, mase, rmse, bias, interval_coverage,
                   validation_points, failure_detail
            FROM read_parquet(?)
            WHERE (? IS NULL OR store_id = ?)
              AND (
                  ? = '' OR contains(lower(sku), lower(?))
                  OR contains(lower(product_name), lower(?))
                  OR contains(lower(category), lower(?))
              )
            ORDER BY CASE WHEN status = 'failed' THEN 0 ELSE 1 END, sku
            LIMIT ?
            """,
            [
                str(path.resolve()),
                store_id,
                store_id,
                query,
                query,
                query,
                query,
                limit,
            ],
        )
        return tuple(
            ForecastSeriesResult(
                run_id=str(row[0]),
                store_id=str(row[1]),
                product_id=str(row[2]),
                sku=str(row[3]),
                product_name=str(row[4]),
                category=str(row[5]),
                status=cast(SeriesRunStatus, str(row[6])),
                selected_model=str(row[7]) if row[7] is not None else None,
                wape=_optional_float(row[8]),
                mase=_optional_float(row[9]),
                rmse=_optional_float(row[10]),
                bias=_optional_float(row[11]),
                interval_coverage=_optional_float(row[12]),
                validation_points=int(row[13]) if row[13] is not None else None,
                failure_detail=str(row[14]) if row[14] is not None else None,
            )
            for row in rows
        )

    def get_evaluations(
        self, run_id: str, store_id: str, product_id: str
    ) -> tuple[StoredModelEvaluation, ...]:
        path = self._artifact_path(run_id, "forecast_model_evaluations.parquet")
        if path is None:
            return ()
        rows = self._fetchall(
            """
            SELECT run_id, store_id, product_id, sku, model_name, selected, status,
                   validation_origins, wape, mase, rmse, bias, interval_coverage,
                   validation_points, failure_detail
            FROM read_parquet(?)
            WHERE store_id = ? AND product_id = ?
            ORDER BY selected DESC, model_name
            """,
            [str(path.resolve()), store_id, product_id],
        )
        return tuple(
            StoredModelEvaluation(
                run_id=str(row[0]),
                store_id=str(row[1]),
                product_id=str(row[2]),
                sku=str(row[3]),
                model_name=str(row[4]),
                selected=bool(row[5]),
                status=cast(EvaluationStatus, str(row[6])),
                validation_origins=int(row[7]),
                wape=_optional_float(row[8]),
                mase=_optional_float(row[9]),
                rmse=_optional_float(row[10]),
                bias=_optional_float(row[11]),
                interval_coverage=_optional_float(row[12]),
                validation_points=int(row[13]) if row[13] is not None else None,
                failure_detail=str(row[14]) if row[14] is not None else None,
            )
            for row in rows
        )

    def get_forecasts(
        self, run_id: str, store_id: str, product_id: str
    ) -> tuple[StoredForecast, ...]:
        path = self._artifact_path(run_id, "forecasts.parquet")
        if path is None:
            return ()
        rows = self._fetchall(
            """
            SELECT run_id, store_id, product_id, sku, period_start, forecast_value,
                   lower_bound, upper_bound, horizon, selected_model, training_cutoff
            FROM read_parquet(?)
            WHERE store_id = ? AND product_id = ?
            ORDER BY horizon
            """,
            [str(path.resolve()), store_id, product_id],
        )
        return tuple(
            StoredForecast(
                run_id=str(row[0]),
                store_id=str(row[1]),
                product_id=str(row[2]),
                sku=str(row[3]),
                period_start=cast(date, row[4]),
                forecast_value=float(row[5]),
                lower_bound=float(row[6]),
                upper_bound=float(row[7]),
                horizon=int(row[8]),
                selected_model=str(row[9]),
                training_cutoff=cast(date, row[10]),
            )
            for row in rows
        )


def _optional_float(value: Any) -> float | None:
    return float(value) if value is not None else None


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as artifact_file:
        for chunk in iter(lambda: artifact_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
