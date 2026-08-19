# 2. Forecasting engine implemented from first principles on numpy

## Status
Accepted

## Context
The forecasting engine needs naive/trend/seasonal models with backtesting and
automatic model selection. Established options: `statsmodels`
(`ExponentialSmoothing`, `SARIMAX`), Facebook `prophet`, or hand-rolled numpy.

## Decision
Implement naive, moving-average, linear-trend, Holt linear, seasonal-naive,
and Holt-Winters from first principles on top of `numpy` only.

## Consequences
- One fewer heavyweight, version-sensitive dependency (`statsmodels` and
  especially `prophet`/`pystan` are notoriously heavy to install and pin,
  particularly across platforms).
- Full control over edge-case behaviour that matters for this domain
  specifically: demand can't be negative (clipped), missing periods are
  gap-filled with zero rather than dropped, and WAPE — not the library's
  default metric — drives model selection because it stays defined when a
  period has zero actual demand (routine for slow-moving SKUs), unlike MAPE.
- Every algorithm is a small, independently unit-testable pure function
  (`(series, horizon, seasonal_periods) -> AlgorithmResult`), which is what
  let the 30+ algorithm-level unit tests in `test_algorithms.py` be written
  quickly and run without any statistical-library version drift changing
  results between environments.
- Tradeoff: no ARIMA/SARIMA, no automatic changepoint detection, no
  holiday-effects modeling the way `prophet` provides out of the box. If the
  product later needs those, `statsmodels`/`prophet` can be added as an
  additional entry in the `ALGORITHMS` registry in
  `services/forecasting/algorithms.py` without touching the engine's
  selection/backtesting/interval logic — that seam was designed in
  deliberately.

## Alternatives considered
- **`statsmodels.tsa.holtwinters.ExponentialSmoothing`**: would have saved
  ~150 lines but pulls in `scipy`/`statsmodels` and their C extensions, and
  its default optimizer occasionally fails to converge on short/synthetic
  series without manual bounds — the grid-search approach used here is more
  predictable for the deliberately short histories this system routinely
  sees (new products, 4–6 months of data).
- **`prophet`**: aimed at daily data with holiday effects; overkill for
  monthly SKU-level planning and a much heavier install (requires a C++
  toolchain via `cmdstanpy` on some platforms).
