"""The forecast engine: model selection, fitting, and uncertainty bands.

The engine is deliberately free of database and web concerns. It takes a list
of :class:`Observation` values and returns a :class:`ForecastResult`, which the
service layer persists. That separation is what makes the whole forecasting
behaviour unit-testable without any infrastructure.

Selection strategy
------------------
1. Reserve the last ``holdout`` periods of history as a hidden test set.
2. Fit every applicable algorithm on the remaining history and score its
   predictions over the holdout using WAPE.
3. Refit the winner on the *full* history and project ``horizon`` periods.
4. Size the prediction interval from the residuals of the refit model.

If the history is too short for a holdout, the engine falls back to in-sample
scoring and records that in the result so the UI can flag lower confidence.
"""

from __future__ import annotations

from datetime import date

import numpy as np

from app.core.config import settings
from app.core.errors import InsufficientHistoryError
from app.core.logging import get_logger
from app.models.enums import ForecastModel
from app.services.forecasting import metrics as metric_fns
from app.services.forecasting.algorithms import ALGORITHMS, AlgorithmNotApplicable
from app.services.forecasting.types import (
    AccuracyMetrics,
    ForecastPoint,
    ForecastResult,
    Observation,
)

logger = get_logger(__name__)

#: Two-sided normal quantiles for the confidence levels the API exposes.
_Z_SCORES = {0.80: 1.2816, 0.90: 1.6449, 0.95: 1.9600, 0.99: 2.5758}


def add_months(anchor: date, months: int) -> date:
    """Return ``anchor`` shifted by ``months``, normalised to the 1st.

    The application's grain is monthly periods keyed on the first of the month,
    so day-of-month arithmetic (and its end-of-month edge cases) never arises.
    """
    total = (anchor.year * 12 + anchor.month - 1) + months
    year, month = divmod(total, 12)
    return date(year, month + 1, 1)


def normalise_period(value: date) -> date:
    """Snap any date to the first day of its month."""
    return date(value.year, value.month, 1)


class ForecastEngine:
    """Produces demand forecasts from a history of monthly observations."""

    def __init__(
        self,
        *,
        seasonal_periods: int | None = None,
        min_history_periods: int | None = None,
        holdout_periods: int | None = None,
        confidence_level: float = 0.95,
    ) -> None:
        self.seasonal_periods = seasonal_periods or settings.forecast_seasonal_periods
        self.min_history_periods = min_history_periods or settings.forecast_min_history_periods
        self.holdout_periods = (
            holdout_periods if holdout_periods is not None else settings.forecast_backtest_holdout
        )
        self.confidence_level = confidence_level

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def forecast(
        self,
        observations: list[Observation],
        *,
        horizon: int = 6,
        model: str = ForecastModel.AUTO.value,
    ) -> ForecastResult:
        """Forecast ``horizon`` future periods from ``observations``.

        Raises :class:`InsufficientHistoryError` when there is not enough
        history to say anything defensible.
        """
        if horizon < 1:
            raise ValueError("horizon must be at least 1")

        series, last_period = self._prepare(observations)

        if series.size < self.min_history_periods:
            raise InsufficientHistoryError(
                f"Need at least {self.min_history_periods} periods of history, "
                f"got {series.size}.",
                details={"periods_available": int(series.size)},
            )

        if model == ForecastModel.AUTO.value:
            chosen, backtest_metrics, scoreboard = self._select_model(series, horizon)
        else:
            if model not in ALGORITHMS:
                raise ValueError(f"Unknown forecast model: {model}")
            chosen = model
            backtest_metrics, scoreboard = self._score_single(series, model, horizon)

        try:
            fit = ALGORITHMS[chosen](series, horizon, self.seasonal_periods)
        except AlgorithmNotApplicable as exc:
            raise InsufficientHistoryError(
                f"Model '{chosen}' cannot be applied to this series: {exc}",
                details={"periods_available": int(series.size), "model": chosen},
            ) from exc

        points = self._build_points(
            series=series,
            fit_forecast=fit.forecast,
            fitted=fit.fitted,
            last_period=last_period,
            horizon=horizon,
        )

        return ForecastResult(
            model_used=chosen,
            points=points,
            metrics=backtest_metrics,
            params=fit.params,
            confidence_level=self.confidence_level,
            history_periods=int(series.size),
            candidates_evaluated=scoreboard,
        )

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _prepare(self, observations: list[Observation]) -> tuple[np.ndarray, date]:
        """Sort, de-duplicate and gap-fill the history onto a dense monthly grid.

        Missing months are filled with zero demand rather than skipped: a month
        with no sales is information, and leaving a hole would silently distort
        every seasonal model.
        """
        if not observations:
            raise InsufficientHistoryError(
                "No sales history available for this product.",
                details={"periods_available": 0},
            )

        by_period: dict[date, float] = {}
        for observation in observations:
            period = normalise_period(observation.period_start)
            by_period[period] = by_period.get(period, 0.0) + float(observation.units)

        first = min(by_period)
        last = max(by_period)
        span = (last.year - first.year) * 12 + (last.month - first.month) + 1

        dense = [by_period.get(add_months(first, offset), 0.0) for offset in range(span)]
        return np.asarray(dense, dtype=float), last

    def _applicable_models(self, length: int) -> list[str]:
        """Candidate models that can actually be fitted to a series this long."""
        candidates = [
            ForecastModel.NAIVE.value,
            ForecastModel.MOVING_AVERAGE.value,
        ]
        if length >= 3:
            candidates.append(ForecastModel.LINEAR_TREND.value)
            candidates.append(ForecastModel.HOLT_LINEAR.value)
        if length >= self.seasonal_periods:
            candidates.append(ForecastModel.SEASONAL_NAIVE.value)
        if length >= 2 * self.seasonal_periods:
            candidates.append(ForecastModel.HOLT_WINTERS.value)
        return candidates

    def _select_model(
        self, series: np.ndarray, horizon: int
    ) -> tuple[str, AccuracyMetrics, dict[str, float | None]]:
        """Backtest every applicable model and return the most accurate one."""
        holdout = self._effective_holdout(series.size)
        scoreboard: dict[str, float | None] = {}
        best_name: str | None = None
        best_score: float | None = None
        best_metrics: AccuracyMetrics | None = None

        for name in self._applicable_models(series.size):
            evaluated = self._backtest(series, name, holdout)
            if evaluated is None:
                scoreboard[name] = None
                continue
            scoreboard[name] = evaluated.wape
            if evaluated.wape is None:
                continue
            if best_score is None or evaluated.wape < best_score:
                best_score = evaluated.wape
                best_name = name
                best_metrics = evaluated

        if best_name is None or best_metrics is None:
            # Nothing scored (e.g. a holdout of pure zeros) — fall back to the
            # naive benchmark rather than refusing to produce a plan.
            logger.debug("no model scored; defaulting to naive")
            return ForecastModel.NAIVE.value, AccuracyMetrics(None, None, None), scoreboard

        return best_name, best_metrics, scoreboard

    def _score_single(
        self, series: np.ndarray, model: str, horizon: int
    ) -> tuple[AccuracyMetrics, dict[str, float | None]]:
        holdout = self._effective_holdout(series.size)
        evaluated = self._backtest(series, model, holdout)
        if evaluated is None:
            return AccuracyMetrics(None, None, None), {model: None}
        return evaluated, {model: evaluated.wape}

    def _effective_holdout(self, length: int) -> int:
        """Never hold out so much that the training window becomes unusable."""
        return max(0, min(self.holdout_periods, length - 2))

    def _backtest(self, series: np.ndarray, model: str, holdout: int) -> AccuracyMetrics | None:
        """Score ``model`` on a hidden tail of the series (or in-sample if too short)."""
        algorithm = ALGORITHMS[model]

        if holdout >= 1:
            train, test = series[:-holdout], series[-holdout:]
            try:
                fit = algorithm(train, holdout, self.seasonal_periods)
            except AlgorithmNotApplicable:
                return None
            return metric_fns.evaluate(test, fit.forecast)

        try:
            fit = algorithm(series, 1, self.seasonal_periods)
        except AlgorithmNotApplicable:
            return None
        # Skip the first fitted value: it is the seeded state, not a prediction.
        return metric_fns.evaluate(series[1:], fit.fitted[1:])

    def _build_points(
        self,
        *,
        series: np.ndarray,
        fit_forecast: np.ndarray,
        fitted: np.ndarray,
        last_period: date,
        horizon: int,
    ) -> list[ForecastPoint]:
        """Attach calendar periods and prediction intervals to the raw path."""
        sigma = self._residual_sigma(series, fitted)
        z = _Z_SCORES.get(round(self.confidence_level, 2), 1.96)

        points: list[ForecastPoint] = []
        for step in range(horizon):
            period = add_months(last_period, step + 1)
            value = float(fit_forecast[step])
            # Uncertainty widens with the square root of the horizon, the
            # standard random-walk assumption for multi-step errors.
            spread = z * sigma * np.sqrt(step + 1)
            points.append(
                ForecastPoint(
                    period_start=period,
                    forecast_units=round(value, 2),
                    lower_bound_units=round(max(0.0, value - spread), 2),
                    upper_bound_units=round(value + spread, 2),
                )
            )
        return points

    @staticmethod
    def _residual_sigma(series: np.ndarray, fitted: np.ndarray) -> float:
        """Standard deviation of one-step-ahead residuals, with a sane floor."""
        residuals = series[1:] - fitted[1:]
        residuals = residuals[np.isfinite(residuals)]
        if residuals.size < 2:
            return float(abs(series.mean()) * 0.10)
        sigma = float(np.std(residuals, ddof=1))
        if not np.isfinite(sigma) or sigma == 0.0:
            # A perfectly-fitted series still carries real-world uncertainty.
            return float(abs(series.mean()) * 0.05)
        return sigma
