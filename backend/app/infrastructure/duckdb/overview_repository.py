"""DuckDB aggregate reads for the portfolio Overview."""

import re
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any, cast

import duckdb

from app.domain import OverviewDemandPoint, OverviewSeriesEvidence

_SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9._-]+$")


class DuckDBOverviewRepository:
    """Query base data and one verified forecast run into bounded read models."""

    def __init__(self, artifact_directory: Path, forecast_run_directory: Path) -> None:
        self._artifact_directory = artifact_directory
        self._forecast_run_directory = forecast_run_directory

    def _base_path(self, filename: str) -> str:
        return str((self._artifact_directory / filename).resolve())

    def _run_path(self, run_id: str, filename: str) -> str | None:
        if not _SAFE_RUN_ID.fullmatch(run_id):
            return None
        path = self._forecast_run_directory / run_id / filename
        return str(path.resolve()) if path.is_file() else None

    @staticmethod
    def _fetchall(sql: str, parameters: Sequence[object]) -> list[tuple[Any, ...]]:
        connection = duckdb.connect(database=":memory:")
        try:
            return connection.execute(sql, parameters).fetchall()
        finally:
            connection.close()

    def get_timeline(self, run_id: str, *, store_id: str | None) -> tuple[OverviewDemandPoint, ...]:
        forecasts = self._run_path(run_id, "forecasts.parquet")
        if forecasts is None:
            return ()
        rows = self._fetchall(
            """
            WITH demand_cutoff AS (
                SELECT max(period_start) AS cutoff
                FROM read_parquet(?)
            ),
            actuals AS (
                SELECT period_start, sum(demand_units)::BIGINT AS actual_units
                FROM read_parquet(?), demand_cutoff
                WHERE period_start >= cutoff - INTERVAL 23 MONTH
                  AND (? IS NULL OR store_id = ?)
                GROUP BY period_start
            ),
            predictions AS (
                SELECT period_start, sum(forecast_value)::DOUBLE AS forecast_units
                FROM read_parquet(?)
                WHERE run_id = ? AND (? IS NULL OR store_id = ?)
                GROUP BY period_start
            )
            SELECT coalesce(a.period_start, p.period_start) AS period_start,
                   a.actual_units, p.forecast_units
            FROM actuals AS a
            FULL OUTER JOIN predictions AS p USING (period_start)
            ORDER BY period_start
            """,
            [
                self._base_path("demand_history.parquet"),
                self._base_path("demand_history.parquet"),
                store_id,
                store_id,
                forecasts,
                run_id,
                store_id,
                store_id,
            ],
        )
        return tuple(
            OverviewDemandPoint(
                period_start=cast(date, row[0]),
                actual_units=int(row[1]) if row[1] is not None else None,
                forecast_units=float(row[2]) if row[2] is not None else None,
            )
            for row in rows
        )

    def get_series_evidence(
        self, run_id: str, *, store_id: str | None
    ) -> tuple[OverviewSeriesEvidence, ...]:
        forecasts = self._run_path(run_id, "forecasts.parquet")
        results = self._run_path(run_id, "forecast_series_results.parquet")
        if forecasts is None or results is None:
            return ()
        rows = self._fetchall(
            """
            WITH forecast_evidence AS (
                SELECT
                    f.store_id,
                    f.product_id,
                    sum(
                        f.forecast_value
                        * greatest(
                            0,
                            date_diff(
                                'day',
                                greatest(cast(i.snapshot_at AS DATE), f.period_start),
                                least(
                                    cast(i.snapshot_at AS DATE) + i.lead_time_days,
                                    cast(f.period_start + INTERVAL 1 MONTH AS DATE)
                                )
                            )
                        )
                        / day(last_day(f.period_start))
                    )::DOUBLE AS lead_time_demand,
                    sum(
                        greatest(
                            0,
                            date_diff(
                                'day',
                                greatest(cast(i.snapshot_at AS DATE), f.period_start),
                                least(
                                    cast(i.snapshot_at AS DATE) + i.lead_time_days,
                                    cast(f.period_start + INTERVAL 1 MONTH AS DATE)
                                )
                            )
                        )
                    )::INTEGER AS covered_days,
                    avg(f.forecast_value)::DOUBLE AS average_forecast,
                    avg(f.upper_bound - f.lower_bound)::DOUBLE AS average_interval_width
                FROM read_parquet(?) AS f
                INNER JOIN read_parquet(?) AS i
                    ON i.store_id = f.store_id AND i.product_id = f.product_id
                WHERE f.run_id = ? AND (? IS NULL OR f.store_id = ?)
                GROUP BY f.store_id, f.product_id
            )
            SELECT
                r.store_id,
                s.store_name,
                r.product_id,
                r.sku,
                r.product_name,
                r.category,
                r.selected_model,
                r.wape,
                r.mase,
                r.bias,
                r.interval_coverage,
                r.validation_points,
                i.on_hand - i.allocated AS available_inventory,
                i.on_order_due_within_lead_time,
                i.safety_stock,
                i.lead_time_days,
                e.covered_days,
                e.lead_time_demand,
                e.average_forecast,
                e.average_interval_width
            FROM read_parquet(?) AS r
            INNER JOIN forecast_evidence AS e
                ON e.store_id = r.store_id AND e.product_id = r.product_id
            INNER JOIN read_parquet(?) AS i
                ON i.store_id = r.store_id AND i.product_id = r.product_id
            INNER JOIN read_parquet(?) AS s ON s.store_id = r.store_id
            WHERE r.run_id = ? AND r.status = 'succeeded'
              AND (? IS NULL OR r.store_id = ?)
            ORDER BY r.store_id, r.sku
            """,
            [
                forecasts,
                self._base_path("inventory_snapshots.parquet"),
                run_id,
                store_id,
                store_id,
                results,
                self._base_path("inventory_snapshots.parquet"),
                self._base_path("stores.parquet"),
                run_id,
                store_id,
                store_id,
            ],
        )
        return tuple(
            OverviewSeriesEvidence(
                store_id=str(row[0]),
                store_name=str(row[1]),
                product_id=str(row[2]),
                sku=str(row[3]),
                product_name=str(row[4]),
                category=str(row[5]),
                selected_model=str(row[6]),
                wape=_optional_float(row[7]),
                mase=_optional_float(row[8]),
                bias=_optional_float(row[9]),
                interval_coverage=_optional_float(row[10]),
                validation_points=int(row[11]) if row[11] is not None else None,
                available_inventory=int(row[12]),
                on_order_due_within_lead_time=int(row[13]),
                safety_stock=int(row[14]),
                lead_time_days=int(row[15]),
                covered_lead_time_days=int(row[16]),
                forecast_demand_during_lead_time=float(row[17]),
                average_monthly_forecast=float(row[18]),
                average_interval_width=float(row[19]),
            )
            for row in rows
        )


def _optional_float(value: Any) -> float | None:
    return float(value) if value is not None else None
