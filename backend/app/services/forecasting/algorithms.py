"""Forecasting algorithms.

Each algorithm is a pure function ``(series, horizon, seasonal_periods) ->
AlgorithmResult``. They operate on a plain ``numpy`` array of demand values in
chronological order and return both the future path and the in-sample fitted
values, which the engine uses to size prediction intervals.

Everything here is implemented from first principles on numpy so the service
has no heavyweight statistical dependency and stays fully deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from app.models.enums import ForecastModel

_SMOOTHING_GRID = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
_TREND_GRID = (0.05, 0.1, 0.2, 0.3, 0.5)
_SEASONAL_GRID = (0.05, 0.1, 0.2, 0.3, 0.5)


@dataclass(slots=True)
class AlgorithmResult:
    """Future path plus the fitted (one-step-ahead) values for the history."""

    forecast: np.ndarray
    fitted: np.ndarray
    params: dict = field(default_factory=dict)


class AlgorithmNotApplicable(Exception):
    """Raised when a series is too short or unsuitable for an algorithm."""


def _as_array(series: np.ndarray | list[float]) -> np.ndarray:
    arr = np.asarray(series, dtype=float)
    if arr.ndim != 1:
        raise AlgorithmNotApplicable("series must be one-dimensional")
    if arr.size == 0:
        raise AlgorithmNotApplicable("series is empty")
    return arr


def _clip_non_negative(values: np.ndarray) -> np.ndarray:
    """Demand cannot be negative; a trend model extrapolating below zero is noise."""
    return np.maximum(values, 0.0)


# --------------------------------------------------------------------------- #
# Baselines
# --------------------------------------------------------------------------- #
def naive(series, horizon: int, seasonal_periods: int = 12) -> AlgorithmResult:
    """Carry the last observed value forward. The benchmark every model must beat."""
    arr = _as_array(series)
    last = float(arr[-1])
    fitted = np.concatenate(([arr[0]], arr[:-1]))
    return AlgorithmResult(
        forecast=_clip_non_negative(np.full(horizon, last)),
        fitted=fitted,
        params={"last_value": last},
    )


def moving_average(
    series, horizon: int, seasonal_periods: int = 12, window: int = 3
) -> AlgorithmResult:
    """Flat forecast at the mean of the last ``window`` periods."""
    arr = _as_array(series)
    effective = min(window, arr.size)
    level = float(arr[-effective:].mean())

    fitted = np.empty_like(arr)
    for index in range(arr.size):
        if index == 0:
            fitted[index] = arr[0]
        else:
            start = max(0, index - effective)
            fitted[index] = arr[start:index].mean()

    return AlgorithmResult(
        forecast=_clip_non_negative(np.full(horizon, level)),
        fitted=fitted,
        params={"window": effective, "level": level},
    )


def seasonal_naive(series, horizon: int, seasonal_periods: int = 12) -> AlgorithmResult:
    """Repeat the value observed one full season ago."""
    arr = _as_array(series)
    m = seasonal_periods
    if arr.size < m:
        raise AlgorithmNotApplicable(
            f"seasonal_naive needs at least {m} observations, got {arr.size}"
        )

    last_season = arr[-m:]
    forecast = np.array([last_season[index % m] for index in range(horizon)], dtype=float)

    fitted = np.empty_like(arr)
    fitted[:m] = arr[:m]
    fitted[m:] = arr[:-m]

    return AlgorithmResult(
        forecast=_clip_non_negative(forecast),
        fitted=fitted,
        params={"seasonal_periods": m},
    )


def linear_trend(series, horizon: int, seasonal_periods: int = 12) -> AlgorithmResult:
    """Ordinary least squares fit of demand against the period index.

    This is the model behind the worked example in the project brief: a series
    of 100, 120, 140, 160 extends to 180.
    """
    arr = _as_array(series)
    if arr.size < 2:
        raise AlgorithmNotApplicable("linear_trend needs at least 2 observations")

    x = np.arange(arr.size, dtype=float)
    slope, intercept = np.polyfit(x, arr, 1)

    future_x = np.arange(arr.size, arr.size + horizon, dtype=float)
    forecast = intercept + slope * future_x
    fitted = intercept + slope * x

    return AlgorithmResult(
        forecast=_clip_non_negative(forecast),
        fitted=fitted,
        params={"slope": float(slope), "intercept": float(intercept)},
    )


# --------------------------------------------------------------------------- #
# Exponential smoothing family
# --------------------------------------------------------------------------- #
def _holt_pass(arr: np.ndarray, alpha: float, beta: float) -> tuple[np.ndarray, float, float]:
    """Run the Holt linear method, returning fitted values and the final state."""
    level = float(arr[0])
    trend = float(arr[1] - arr[0]) if arr.size > 1 else 0.0
    fitted = np.empty_like(arr)
    fitted[0] = level

    for index in range(1, arr.size):
        prediction = level + trend
        fitted[index] = prediction
        previous_level = level
        level = alpha * arr[index] + (1 - alpha) * prediction
        trend = beta * (level - previous_level) + (1 - beta) * trend

    return fitted, level, trend


def holt_linear(series, horizon: int, seasonal_periods: int = 12) -> AlgorithmResult:
    """Double exponential smoothing with a grid search over alpha and beta."""
    arr = _as_array(series)
    if arr.size < 3:
        raise AlgorithmNotApplicable("holt_linear needs at least 3 observations")

    best: tuple[float, float, float] | None = None
    best_state: tuple[np.ndarray, float, float] | None = None

    for alpha in _SMOOTHING_GRID:
        for beta in _TREND_GRID:
            fitted, level, trend = _holt_pass(arr, alpha, beta)
            sse = float(np.sum((arr[1:] - fitted[1:]) ** 2))
            if best is None or sse < best[0]:
                best = (sse, alpha, beta)
                best_state = (fitted, level, trend)

    if best is None or best_state is None:  # pragma: no cover - grids are non-empty
        raise AlgorithmNotApplicable("holt_linear failed to fit")

    _, alpha, beta = best
    fitted, level, trend = best_state
    forecast = np.array([level + (step + 1) * trend for step in range(horizon)], dtype=float)

    return AlgorithmResult(
        forecast=_clip_non_negative(forecast),
        fitted=fitted,
        params={"alpha": alpha, "beta": beta, "level": level, "trend": trend},
    )


def _initial_seasonal_indices(arr: np.ndarray, m: int) -> np.ndarray:
    """Additive seasonal starting values averaged over every complete season."""
    seasons = arr.size // m
    matrix = arr[: seasons * m].reshape(seasons, m)
    season_means = matrix.mean(axis=1, keepdims=True)
    detrended = matrix - season_means
    indices = detrended.mean(axis=0)
    # Additive seasonality must sum to zero so it does not absorb the level.
    return indices - indices.mean()


def _holt_winters_pass(
    arr: np.ndarray, m: int, alpha: float, beta: float, gamma: float
) -> tuple[np.ndarray, float, float, np.ndarray]:
    seasonal = _initial_seasonal_indices(arr, m).copy()
    level = float(arr[:m].mean())
    trend = float((arr[m:2 * m].mean() - arr[:m].mean()) / m) if arr.size >= 2 * m else 0.0

    fitted = np.empty_like(arr)

    for index in range(arr.size):
        season_index = index % m
        prediction = level + trend + seasonal[season_index]
        fitted[index] = prediction

        previous_level = level
        deseasonalised = arr[index] - seasonal[season_index]
        level = alpha * deseasonalised + (1 - alpha) * (previous_level + trend)
        trend = beta * (level - previous_level) + (1 - beta) * trend
        seasonal[season_index] = gamma * (arr[index] - level) + (1 - gamma) * seasonal[season_index]

    return fitted, level, trend, seasonal


def holt_winters(series, horizon: int, seasonal_periods: int = 12) -> AlgorithmResult:
    """Triple exponential smoothing with additive seasonality.

    Requires two complete seasons so the seasonal indices are estimated from
    more than a single cycle.
    """
    arr = _as_array(series)
    m = seasonal_periods
    if m < 2:
        raise AlgorithmNotApplicable("seasonal_periods must be at least 2")
    if arr.size < 2 * m:
        raise AlgorithmNotApplicable(
            f"holt_winters needs at least {2 * m} observations, got {arr.size}"
        )

    best_sse: float | None = None
    best: tuple[np.ndarray, float, float, np.ndarray, float, float, float] | None = None

    for alpha in (0.1, 0.3, 0.5, 0.7, 0.9):
        for beta in _TREND_GRID:
            for gamma in _SEASONAL_GRID:
                fitted, level, trend, seasonal = _holt_winters_pass(arr, m, alpha, beta, gamma)
                sse = float(np.sum((arr[m:] - fitted[m:]) ** 2))
                if not np.isfinite(sse):
                    continue
                if best_sse is None or sse < best_sse:
                    best_sse = sse
                    best = (fitted, level, trend, seasonal, alpha, beta, gamma)

    if best is None:  # pragma: no cover - only reachable with degenerate input
        raise AlgorithmNotApplicable("holt_winters failed to converge on this series")

    fitted, level, trend, seasonal, alpha, beta, gamma = best
    forecast = np.array(
        [level + (step + 1) * trend + seasonal[(arr.size + step) % m] for step in range(horizon)],
        dtype=float,
    )

    return AlgorithmResult(
        forecast=_clip_non_negative(forecast),
        fitted=fitted,
        params={
            "alpha": alpha,
            "beta": beta,
            "gamma": gamma,
            "level": level,
            "trend": trend,
            "seasonal_periods": m,
        },
    )


#: Registry consulted by the engine when running automatic model selection.
ALGORITHMS = {
    ForecastModel.NAIVE.value: naive,
    ForecastModel.MOVING_AVERAGE.value: moving_average,
    ForecastModel.SEASONAL_NAIVE.value: seasonal_naive,
    ForecastModel.LINEAR_TREND.value: linear_trend,
    ForecastModel.HOLT_LINEAR.value: holt_linear,
    ForecastModel.HOLT_WINTERS.value: holt_winters,
}
