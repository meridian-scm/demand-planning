"""Forecast accuracy metrics.

Every function tolerates zeros and empty input by returning ``None`` rather
than raising or producing ``inf`` — a slow-moving SKU with a zero-demand month
is normal, not an error.
"""

from __future__ import annotations

import numpy as np

from app.services.forecasting.types import AccuracyMetrics


def _aligned(actual, predicted) -> tuple[np.ndarray, np.ndarray]:
    a = np.asarray(actual, dtype=float)
    p = np.asarray(predicted, dtype=float)
    if a.size != p.size:
        raise ValueError(f"length mismatch: actual={a.size} predicted={p.size}")
    mask = np.isfinite(a) & np.isfinite(p)
    return a[mask], p[mask]


def mape(actual, predicted) -> float | None:
    """Mean absolute percentage error, ignoring periods with zero actuals."""
    a, p = _aligned(actual, predicted)
    non_zero = a != 0
    if not non_zero.any():
        return None
    return float(np.mean(np.abs((a[non_zero] - p[non_zero]) / a[non_zero])) * 100.0)


def wape(actual, predicted) -> float | None:
    """Weighted absolute percentage error: sum|error| / sum|actual|.

    Preferred over MAPE for model selection because it is defined whenever the
    series has any demand at all, and it weights large periods appropriately.
    """
    a, p = _aligned(actual, predicted)
    denominator = float(np.sum(np.abs(a)))
    if denominator == 0:
        return None
    return float(np.sum(np.abs(a - p)) / denominator * 100.0)


def rmse(actual, predicted) -> float | None:
    """Root mean squared error."""
    a, p = _aligned(actual, predicted)
    if a.size == 0:
        return None
    return float(np.sqrt(np.mean((a - p) ** 2)))


def bias(actual, predicted) -> float | None:
    """Mean signed error as a percentage of mean demand.

    Positive means the model over-forecasts, which is what drives excess stock.
    """
    a, p = _aligned(actual, predicted)
    if a.size == 0:
        return None
    mean_actual = float(np.mean(a))
    if mean_actual == 0:
        return None
    return float(np.mean(p - a) / mean_actual * 100.0)


def evaluate(actual, predicted) -> AccuracyMetrics:
    """Compute the full metric set for one actual/prediction pair."""
    return AccuracyMetrics(
        mape=mape(actual, predicted),
        wape=wape(actual, predicted),
        rmse=rmse(actual, predicted),
        bias=bias(actual, predicted),
    )
