"""Deterministic rolling-origin model evaluation and forecast selection."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from math import sqrt
from statistics import fmean

import numpy as np

from app.domain.forecasting import (
    ForecastMetrics,
    ForecastPoint,
    ForecastResult,
    ModelEvaluation,
)
from app.ports.forecasting import ForecastModel, ModelPrediction


class InsufficientHistoryError(ValueError):
    """Raised when honest rolling-origin validation cannot be performed."""


class ForecastingFailedError(RuntimeError):
    """Raised when every eligible candidate fails to fit."""


@dataclass(frozen=True, slots=True)
class _CandidateOutcome:
    model: ForecastModel
    evaluation: ModelEvaluation
    absolute_errors: tuple[float, ...]


def calculate_metrics(
    actual: Sequence[float],
    predicted: Sequence[float],
    *,
    mase_denominators: Sequence[float | None],
    lower: Sequence[float] | None = None,
    upper: Sequence[float] | None = None,
) -> ForecastMetrics:
    """Calculate metrics without disguising undefined denominators as zero."""

    if not actual or len(actual) != len(predicted) or len(actual) != len(mase_denominators):
        raise ValueError("metric inputs must be non-empty and have equal lengths")
    errors = [forecast - observed for observed, forecast in zip(actual, predicted, strict=True)]
    absolute_errors = [abs(error) for error in errors]
    actual_denominator = sum(abs(value) for value in actual)
    valid_scaled_errors = [
        error / denominator
        for error, denominator in zip(absolute_errors, mase_denominators, strict=True)
        if denominator is not None and denominator > 0
    ]
    coverage: float | None = None
    if lower is not None and upper is not None:
        if len(lower) != len(actual) or len(upper) != len(actual):
            raise ValueError("prediction interval inputs must match actual values")
        coverage = fmean(
            low <= observed <= high
            for observed, low, high in zip(actual, lower, upper, strict=True)
        )
    return ForecastMetrics(
        wape=(sum(absolute_errors) / actual_denominator if actual_denominator else None),
        mase=(fmean(valid_scaled_errors) if valid_scaled_errors else None),
        rmse=sqrt(fmean(error * error for error in errors)),
        bias=(sum(errors) / actual_denominator if actual_denominator else None),
        interval_coverage=coverage,
        validation_points=len(actual),
    )


def _add_months(period: date, months: int) -> date:
    month_index = period.year * 12 + period.month - 1 + months
    return date(month_index // 12, month_index % 12 + 1, 1)


def _mase_scale(training: tuple[float, ...], season_length: int = 12) -> float | None:
    if len(training) <= season_length:
        return None
    differences = [
        abs(training[index] - training[index - season_length])
        for index in range(season_length, len(training))
    ]
    scale = fmean(differences)
    return scale if scale > 0 else None


class ForecastingEngine:
    """Compare a controlled candidate set using expanding-window validation."""

    def __init__(
        self,
        model_factory: Callable[..., tuple[ForecastModel, ...]],
        *,
        minimum_training_months: int = 36,
        maximum_origins: int = 4,
        minimum_origins: int = 2,
    ) -> None:
        self._model_factory = model_factory
        self._minimum_training_months = minimum_training_months
        self._maximum_origins = maximum_origins
        self._minimum_origins = minimum_origins

    def run(
        self,
        history: Sequence[int | float],
        *,
        training_cutoff: date,
        horizon: int,
        interval_level: int = 90,
    ) -> ForecastResult:
        if not 1 <= horizon <= 12:
            raise ValueError("horizon must be between 1 and 12 months")
        if not 50 <= interval_level <= 99:
            raise ValueError("interval_level must be between 50 and 99")
        values = tuple(float(value) for value in history)
        if not values or any(not np.isfinite(value) or value < 0 for value in values):
            raise ValueError("history must contain finite nonnegative demand")
        if all(value == 0 for value in values):
            return self._zero_result(values, training_cutoff, horizon, interval_level)

        origins = list(range(self._minimum_training_months, len(values) - horizon + 1, horizon))[
            -self._maximum_origins :
        ]
        if len(origins) < self._minimum_origins:
            required = self._minimum_training_months + self._minimum_origins * horizon
            raise InsufficientHistoryError(
                f"At least {required} completed months are required for "
                f"{horizon}-month validation; "
                f"received {len(values)}."
            )

        intermittent = sum(value == 0 for value in values) / len(values) >= 0.4
        models = self._model_factory(intermittent=intermittent)
        outcomes = tuple(
            self._evaluate(model, values, origins, horizon, interval_level) for model in models
        )
        succeeded = [outcome for outcome in outcomes if outcome.evaluation.metrics is not None]
        if not succeeded:
            raise ForecastingFailedError("Every eligible forecasting candidate failed.")
        winner = min(succeeded, key=self._selection_key)
        final_prediction = winner.model.predict(values, horizon, interval_level)
        lower, upper = self._final_intervals(
            final_prediction, winner.absolute_errors, interval_level
        )
        forecasts = tuple(
            ForecastPoint(
                period_start=_add_months(training_cutoff, step),
                forecast_value=max(0.0, final_prediction.mean[step - 1]),
                lower_bound=max(0.0, lower[step - 1]),
                upper_bound=max(0.0, upper[step - 1]),
                horizon=step,
            )
            for step in range(1, horizon + 1)
        )
        metrics = winner.evaluation.metrics
        assert metrics is not None
        identity = "|".join(
            [training_cutoff.isoformat(), str(horizon), winner.model.name]
            + [f"{value:.8f}" for value in values]
        )
        return ForecastResult(
            forecast_id=f"preview-{sha256(identity.encode()).hexdigest()[:16]}",
            selected_model=winner.model.name,
            training_cutoff=training_cutoff,
            horizon_months=horizon,
            interval_level=interval_level,
            intermittent_demand=intermittent,
            validation_origins=len(origins),
            selected_metrics=metrics,
            evaluations=tuple(outcome.evaluation for outcome in outcomes),
            forecasts=forecasts,
        )

    def _evaluate(
        self,
        model: ForecastModel,
        values: tuple[float, ...],
        origins: list[int],
        horizon: int,
        interval_level: int,
    ) -> _CandidateOutcome:
        actual: list[float] = []
        predicted: list[float] = []
        lower: list[float] = []
        upper: list[float] = []
        scales: list[float | None] = []
        has_intervals = True
        try:
            for origin in origins:
                training = values[:origin]
                validation = values[origin : origin + horizon]
                prediction = model.predict(training, horizon, interval_level)
                if len(prediction.mean) != horizon:
                    raise ValueError("candidate returned an invalid forecast length")
                actual.extend(validation)
                predicted.extend(max(0.0, value) for value in prediction.mean)
                scales.extend([_mase_scale(training)] * horizon)
                if prediction.lower is None or prediction.upper is None:
                    has_intervals = False
                else:
                    lower.extend(max(0.0, value) for value in prediction.lower)
                    upper.extend(max(0.0, value) for value in prediction.upper)
            metrics = calculate_metrics(
                actual,
                predicted,
                mase_denominators=scales,
                lower=lower if has_intervals else None,
                upper=upper if has_intervals else None,
            )
            absolute_errors = tuple(
                abs(observed - forecast)
                for observed, forecast in zip(actual, predicted, strict=True)
            )
            return _CandidateOutcome(
                model=model,
                evaluation=ModelEvaluation(
                    model_name=model.name,
                    status="succeeded",
                    validation_origins=len(origins),
                    metrics=metrics,
                ),
                absolute_errors=absolute_errors,
            )
        except Exception as error:
            return _CandidateOutcome(
                model=model,
                evaluation=ModelEvaluation(
                    model_name=model.name,
                    status="failed",
                    validation_origins=len(origins),
                    metrics=None,
                    failure_detail=f"{type(error).__name__}: {error}",
                ),
                absolute_errors=(),
            )

    @staticmethod
    def _selection_key(outcome: _CandidateOutcome) -> tuple[float, float, float, float, int]:
        metrics = outcome.evaluation.metrics
        assert metrics is not None
        return (
            metrics.wape if metrics.wape is not None else float("inf"),
            metrics.mase if metrics.mase is not None else float("inf"),
            abs(metrics.bias) if metrics.bias is not None else float("inf"),
            metrics.rmse,
            outcome.model.complexity_rank,
        )

    @staticmethod
    def _final_intervals(
        prediction: ModelPrediction, absolute_errors: tuple[float, ...], interval_level: int
    ) -> tuple[tuple[float, ...], tuple[float, ...]]:
        if prediction.lower is not None and prediction.upper is not None:
            return prediction.lower, prediction.upper
        radius = float(
            np.quantile(
                np.asarray(absolute_errors, dtype=np.float64),
                interval_level / 100,
                method="higher",
            )
        )
        return (
            tuple(value - radius for value in prediction.mean),
            tuple(value + radius for value in prediction.mean),
        )

    @staticmethod
    def _zero_result(
        values: tuple[float, ...], training_cutoff: date, horizon: int, interval_level: int
    ) -> ForecastResult:
        metrics = ForecastMetrics(
            wape=None,
            mase=None,
            rmse=0.0,
            bias=None,
            interval_coverage=1.0,
            validation_points=0,
        )
        identity = f"{training_cutoff.isoformat()}|{horizon}|Zero|{len(values)}"
        return ForecastResult(
            forecast_id=f"preview-{sha256(identity.encode()).hexdigest()[:16]}",
            selected_model="Zero",
            training_cutoff=training_cutoff,
            horizon_months=horizon,
            interval_level=interval_level,
            intermittent_demand=True,
            validation_origins=0,
            selected_metrics=metrics,
            evaluations=(
                ModelEvaluation(
                    model_name="Zero",
                    status="succeeded",
                    validation_origins=0,
                    metrics=metrics,
                ),
            ),
            forecasts=tuple(
                ForecastPoint(
                    period_start=_add_months(training_cutoff, step),
                    forecast_value=0.0,
                    lower_bound=0.0,
                    upper_bound=0.0,
                    horizon=step,
                )
                for step in range(1, horizon + 1)
            ),
        )
