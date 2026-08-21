# Scripts

`generate_data.py` is the safe wrapper for the synthetic-data generator. It validates all invariants
before publishing versioned Parquet artifacts and refuses to replace an existing output directory
unless `--overwrite` is explicitly supplied.

`generate_reference_forecasts.py` runs the statistical forecasting engine offline and atomically
publishes immutable, checksum-backed run artifacts. A generated base dataset must already exist.

Verified test-profile command from the repository root:

```bash
backend/.venv/bin/python scripts/generate_reference_forecasts.py --config config/forecast/test.yaml
```

Benchmark the full reference demand layout after generating `reference-v1`:

```bash
backend/.venv/bin/python scripts/benchmark_parquet_layouts.py --runs 15
```

The benchmark creates ignored, disposable alternatives under
`data/generated/benchmarks/reference-v1`, verifies that every layout returns identical results, and
records file count, compressed size, build time, and DuckDB query timings. It refuses to replace an
existing benchmark directory unless `--overwrite` is supplied.

Validate every immutable run below a forecast root:

```bash
backend/.venv/bin/python scripts/validate_forecast_runs.py \
  --forecast-root data/generated/test-v1/forecast_runs
```

Validation verifies manifest checksums and row counts, run-summary consistency, unique keys,
nonnegative ordered prediction intervals, and the expected number of horizons for every successful
Store + SKU series.

The reference configuration exists at `config/forecast/reference.yaml`, but its full 17,500-series
run remains intentionally unexecuted until the final reference-generation step.
