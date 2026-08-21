"""Benchmark candidate Parquet layouts for Meridian demand history."""

from __future__ import annotations

import argparse
import json
import math
import platform
import shutil
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from statistics import median
from typing import Any

import duckdb

DEFAULT_RUNS = 15


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build and benchmark consolidated and partitioned demand Parquet layouts."
    )
    parser.add_argument(
        "--artifact-directory",
        type=Path,
        default=Path("data/generated/reference-v1"),
        help="Published artifact directory containing demand_history.parquet and products.parquet",
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path("data/generated/benchmarks/reference-v1"),
        help="Directory for benchmark-only layouts and benchmark-report.json",
    )
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS, help="Timed runs per query")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing benchmark directory",
    )
    return parser


def _sql_path(path: Path) -> str:
    return str(path.resolve()).replace("'", "''")


def _directory_size(path: Path) -> int:
    return sum(file.stat().st_size for file in path.rglob("*.parquet"))


def _percentile_95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]


def _timed_query(query: str, parameters: Sequence[Any], runs: int) -> dict[str, float]:
    samples: list[float] = []
    for index in range(runs + 2):
        started = time.perf_counter()
        with duckdb.connect(":memory:") as connection:
            connection.execute("SET threads = 1")
            connection.execute(query, parameters).fetchall()
        elapsed_ms = (time.perf_counter() - started) * 1000
        if index >= 2:
            samples.append(elapsed_ms)
    return {
        "median_ms": round(median(samples), 3),
        "p95_ms": round(_percentile_95(samples), 3),
        "minimum_ms": round(min(samples), 3),
    }


def _query_result(query: str, parameters: Sequence[Any]) -> list[tuple[Any, ...]]:
    with duckdb.connect(":memory:") as connection:
        connection.execute("SET threads = 1")
        return connection.execute(query, parameters).fetchall()


def _build_partitioned_layout(
    source: Path,
    destination: Path,
    partition_columns: str,
    projection: str,
) -> float:
    started = time.perf_counter()
    with duckdb.connect(":memory:") as connection:
        connection.execute("SET threads = 1")
        connection.execute(
            f"""
            COPY (
                SELECT {projection}
                FROM read_parquet('{_sql_path(source)}')
                ORDER BY store_id, product_id, period_start
            )
            TO '{_sql_path(destination)}'
            (FORMAT parquet, COMPRESSION zstd, PARTITION_BY ({partition_columns}))
            """
        )
    return round(time.perf_counter() - started, 3)


def _read_expression(path: Path, partitioned: bool) -> str:
    if not partitioned:
        return f"read_parquet('{_sql_path(path)}')"
    return f"read_parquet('{_sql_path(path)}/**/*.parquet', hive_partitioning = true)"


def _benchmark_layout(
    name: str,
    path: Path,
    partitioned: bool,
    products_path: Path,
    runs: int,
) -> tuple[dict[str, Any], dict[str, list[tuple[Any, ...]]]]:
    demand = _read_expression(path, partitioned)
    queries: dict[str, tuple[str, Sequence[Any]]] = {
        "initialize_and_count": (f"SELECT count(*) FROM {demand}", ()),
        "store_sku_history": (
            f"""
            SELECT period_start, demand_units
            FROM {demand}
            WHERE store_id = ? AND product_id = ?
            ORDER BY period_start
            """,
            ("store-003", "product-01750"),
        ),
        "store_recent_monthly_aggregation": (
            f"""
            SELECT period_start, sum(demand_units)
            FROM {demand}
            WHERE store_id = ? AND period_start BETWEEN ? AND ?
            GROUP BY period_start
            ORDER BY period_start
            """,
            ("store-003", "2025-08-01", "2026-07-01"),
        ),
        "portfolio_category_aggregation": (
            f"""
            SELECT products.category, sum(demand.demand_units)
            FROM {demand} AS demand
            JOIN read_parquet('{_sql_path(products_path)}') AS products
              ON products.product_id = demand.product_id
            GROUP BY products.category
            ORDER BY products.category
            """,
            (),
        ),
    }
    timings = {
        query_name: _timed_query(query, parameters, runs)
        for query_name, (query, parameters) in queries.items()
    }
    results = {
        query_name: _query_result(query, parameters)
        for query_name, (query, parameters) in queries.items()
    }
    parquet_files = [path] if path.is_file() else sorted(path.rglob("*.parquet"))
    return (
        {
            "layout": name,
            "path": str(path),
            "file_count": len(parquet_files),
            "size_bytes": path.stat().st_size if path.is_file() else _directory_size(path),
            "queries": timings,
        },
        results,
    )


def _resolve(project_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else project_root / path


def main(arguments: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(arguments)
    if args.runs < 3:
        raise ValueError("--runs must be at least 3")

    project_root = Path(__file__).resolve().parents[1]
    artifact_directory = _resolve(project_root, args.artifact_directory)
    output_directory = _resolve(project_root, args.output_directory)
    demand_path = artifact_directory / "demand_history.parquet"
    products_path = artifact_directory / "products.parquet"
    manifest_path = artifact_directory / "manifest.json"
    for required_path in (demand_path, products_path, manifest_path):
        if not required_path.is_file():
            raise FileNotFoundError(f"Required reference artifact is missing: {required_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if output_directory.exists():
        if not args.overwrite:
            raise FileExistsError(
                f"Benchmark output already exists: {output_directory}. "
                "Use --overwrite to replace it."
            )
        shutil.rmtree(output_directory)
    output_directory.mkdir(parents=True)

    store_path = output_directory / "by_store"
    store_year_path = output_directory / "by_store_year"
    build_seconds = {
        "consolidated": 0.0,
        "by_store": _build_partitioned_layout(
            demand_path,
            store_path,
            "store_id",
            "*",
        ),
        "by_store_year": _build_partitioned_layout(
            demand_path,
            store_year_path,
            "store_id, period_year",
            "*, year(period_start) AS period_year",
        ),
    }

    definitions = (
        ("consolidated", demand_path, False),
        ("by_store", store_path, True),
        ("by_store_year", store_year_path, True),
    )
    layouts: list[dict[str, Any]] = []
    baseline_results: dict[str, list[tuple[Any, ...]]] | None = None
    for name, path, partitioned in definitions:
        layout, results = _benchmark_layout(name, path, partitioned, products_path, args.runs)
        layout["build_seconds"] = build_seconds[name]
        if baseline_results is None:
            baseline_results = results
        elif results != baseline_results:
            raise RuntimeError(f"Layout {name} returned results that differ from consolidated")
        layouts.append(layout)

    report = {
        "artifact_data_version": manifest["data_version"],
        "demand_row_count": baseline_results["initialize_and_count"][0][0]
        if baseline_results
        else 0,
        "selected_layout": "consolidated",
        "runs_per_query": args.runs,
        "methodology": (
            "Two warmups followed by fresh in-memory DuckDB connections for every timed sample; "
            "single-threaded execution with operating-system file cache left intact."
        ),
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "duckdb": duckdb.__version__,
        },
        "layouts": layouts,
    }
    report_path = output_directory / "benchmark-report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
