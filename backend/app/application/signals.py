"""Explainable trend and anomaly detection for monthly demand."""

from __future__ import annotations

from hashlib import sha256
from math import sqrt
from statistics import fmean, median

from app.application.demand_explorer import PlanningDataNotFoundError
from app.domain import DemandObservation, DemandSignal
from app.domain.signals import SignalDirection, SignalSeverity
from app.ports.repositories.planning import PlanningReadRepository

TREND_WINDOW_MONTHS = 12
ROBUST_WINDOW_MONTHS = 24
MINIMUM_ABSOLUTE_TREND_CHANGE = 5.0
TREND_PERCENT_THRESHOLD = 0.10
RELATIVE_SLOPE_THRESHOLD = 0.01
VOLATILITY_THRESHOLD = 0.35
SEASONAL_CORRELATION_THRESHOLD = 0.60
ANOMALY_SCORE_THRESHOLD = 3.5
WARNING_ANOMALY_SCORE = 5.0
MAXIMUM_ANOMALIES = 5


class SignalDetectionService:
    """Retrieve one Store + SKU history and derive stateless demand signals."""

    def __init__(self, repository: PlanningReadRepository) -> None:
        self._repository = repository

    def get_signals(self, store_id: str, product_id: str) -> tuple[DemandSignal, ...]:
        observations = self._repository.get_demand_series(store_id, product_id)
        if not observations:
            raise PlanningDataNotFoundError(
                f"No demand series exists for store {store_id!r} and product {product_id!r}."
            )
        return detect_demand_signals(observations)


def detect_demand_signals(
    observations: tuple[DemandObservation, ...],
) -> tuple[DemandSignal, ...]:
    """Detect a small, deterministic set of interpretable demand signals."""

    if not observations:
        return ()
    ordered = tuple(sorted(observations, key=lambda observation: observation.period_start))
    values = [float(observation.demand_units) for observation in ordered]
    signals = [_detect_trend(ordered, values)]

    volatility = _detect_volatility(ordered, values)
    if volatility is not None:
        signals.append(volatility)
    seasonality = _detect_seasonality(ordered, values)
    if seasonality is not None:
        signals.append(seasonality)
    signals.extend(_detect_anomalies(ordered, values))
    return tuple(signals)


def _detect_trend(observations: tuple[DemandObservation, ...], values: list[float]) -> DemandSignal:
    recent = values[-TREND_WINDOW_MONTHS:]
    prior = values[-2 * TREND_WINDOW_MONTHS : -TREND_WINDOW_MONTHS]
    recent_average = fmean(recent)
    prior_average = fmean(prior) if prior else recent_average
    absolute_change = recent_average - prior_average
    percent_change = absolute_change / max(abs(prior_average), 1.0)
    slope_values = values[-ROBUST_WINDOW_MONTHS:]
    robust_slope = _median_pairwise_slope(slope_values)
    relative_slope = robust_slope / max(fmean(slope_values), 1.0)

    direction: SignalDirection
    severity: SignalSeverity
    if (
        absolute_change >= MINIMUM_ABSOLUTE_TREND_CHANGE
        and percent_change >= TREND_PERCENT_THRESHOLD
        and relative_slope >= RELATIVE_SLOPE_THRESHOLD
    ):
        direction = "growing"
        title = "Demand is growing"
        description = (
            "Recent demand is materially above the prior year and the underlying slope is positive."
        )
        severity = "watch"
    elif (
        absolute_change <= -MINIMUM_ABSOLUTE_TREND_CHANGE
        and percent_change <= -TREND_PERCENT_THRESHOLD
        and relative_slope <= -RELATIVE_SLOPE_THRESHOLD
    ):
        direction = "declining"
        title = "Demand is declining"
        description = (
            "Recent demand is materially below the prior year and the underlying slope is negative."
        )
        severity = "watch"
    else:
        direction = "stable"
        title = "Demand is broadly stable"
        description = "Recent demand does not exceed the material growth or decline thresholds."
        severity = "info"

    latest = observations[-1]
    return DemandSignal(
        signal_id=_signal_id(latest, "trend", direction, latest.period_start.isoformat()),
        store_id=latest.store_id,
        product_id=latest.product_id,
        sku=latest.sku,
        signal_type="trend",
        direction=direction,
        severity=severity,
        period_start=latest.period_start,
        title=title,
        description=description,
        metric_name="recent_vs_prior_year_change",
        metric_value=percent_change,
        baseline_value=prior_average,
        threshold_value=TREND_PERCENT_THRESHOLD,
        evidence={
            "recent_12_month_average": recent_average,
            "prior_12_month_average": prior_average,
            "absolute_change_units": absolute_change,
            "percent_change": percent_change,
            "robust_monthly_slope": robust_slope,
            "relative_monthly_slope": relative_slope,
        },
    )


def _detect_volatility(
    observations: tuple[DemandObservation, ...], values: list[float]
) -> DemandSignal | None:
    sample = values[-ROBUST_WINDOW_MONTHS:]
    sample_median = median(sample)
    robust_dispersion = 1.4826 * median(abs(value - sample_median) for value in sample)
    mean_demand = fmean(sample)
    dispersion_ratio = robust_dispersion / max(mean_demand, 1.0)
    if dispersion_ratio < VOLATILITY_THRESHOLD:
        return None

    latest = observations[-1]
    return DemandSignal(
        signal_id=_signal_id(latest, "volatility", "volatile", latest.period_start.isoformat()),
        store_id=latest.store_id,
        product_id=latest.product_id,
        sku=latest.sku,
        signal_type="volatility",
        direction="volatile",
        severity="watch",
        period_start=latest.period_start,
        title="Demand is volatile",
        description="Recent monthly demand varies materially around its typical level.",
        metric_name="robust_dispersion_ratio",
        metric_value=dispersion_ratio,
        baseline_value=mean_demand,
        threshold_value=VOLATILITY_THRESHOLD,
        evidence={
            "window_months": len(sample),
            "mean_demand": mean_demand,
            "median_demand": sample_median,
            "robust_dispersion_units": robust_dispersion,
            "robust_dispersion_ratio": dispersion_ratio,
        },
    )


def _detect_seasonality(
    observations: tuple[DemandObservation, ...], values: list[float]
) -> DemandSignal | None:
    if len(values) < 36:
        return None
    correlation = _pearson_correlation(values[12:], values[:-12])
    if correlation is None or correlation < SEASONAL_CORRELATION_THRESHOLD:
        return None

    latest = observations[-1]
    return DemandSignal(
        signal_id=_signal_id(latest, "seasonality", "seasonal", latest.period_start.isoformat()),
        store_id=latest.store_id,
        product_id=latest.product_id,
        sku=latest.sku,
        signal_type="seasonality",
        direction="seasonal",
        severity="info",
        period_start=latest.period_start,
        title="Annual seasonality detected",
        description="Monthly demand has a strong relationship with the same months in prior years.",
        metric_name="lag_12_correlation",
        metric_value=correlation,
        baseline_value=None,
        threshold_value=SEASONAL_CORRELATION_THRESHOLD,
        evidence={
            "lag_months": 12,
            "correlation": correlation,
            "paired_observations": len(values) - 12,
        },
    )


def _detect_anomalies(
    observations: tuple[DemandObservation, ...], values: list[float]
) -> list[DemandSignal]:
    anomalies: list[DemandSignal] = []
    for index in range(TREND_WINDOW_MONTHS, len(values)):
        history = values[index - TREND_WINDOW_MONTHS : index]
        baseline = median(history)
        mad = median(abs(value - baseline) for value in history)
        robust_scale = max(1.4826 * mad, sqrt(max(baseline, 1.0)))
        deviation = values[index] - baseline
        score = abs(deviation) / robust_scale
        minimum_change = max(10.0, 0.25 * max(baseline, 1.0))
        if score < ANOMALY_SCORE_THRESHOLD or abs(deviation) < minimum_change:
            continue

        observation = observations[index]
        direction: SignalDirection = "spike" if deviation > 0 else "drop"
        anomalies.append(
            DemandSignal(
                signal_id=_signal_id(
                    observation, "anomaly", direction, observation.period_start.isoformat()
                ),
                store_id=observation.store_id,
                product_id=observation.product_id,
                sku=observation.sku,
                signal_type="anomaly",
                direction=direction,
                severity="warning" if score >= WARNING_ANOMALY_SCORE else "watch",
                period_start=observation.period_start,
                title=f"Demand {direction} detected",
                description=(
                    f"Demand was {'above' if deviation > 0 else 'below'} its trailing 12-month "
                    "baseline by a material amount."
                ),
                metric_name="robust_anomaly_score",
                metric_value=score,
                baseline_value=baseline,
                threshold_value=ANOMALY_SCORE_THRESHOLD,
                evidence={
                    "observed_demand": values[index],
                    "trailing_12_month_median": baseline,
                    "deviation_units": deviation,
                    "robust_anomaly_score": score,
                    "minimum_absolute_change_units": minimum_change,
                },
            )
        )
    return anomalies[-MAXIMUM_ANOMALIES:]


def _median_pairwise_slope(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    slopes = [
        (values[end] - values[start]) / (end - start)
        for start in range(len(values) - 1)
        for end in range(start + 1, len(values))
    ]
    return float(median(slopes))


def _pearson_correlation(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    left_mean = fmean(left)
    right_mean = fmean(right)
    left_deviation = [value - left_mean for value in left]
    right_deviation = [value - right_mean for value in right]
    denominator = sqrt(
        sum(value * value for value in left_deviation)
        * sum(value * value for value in right_deviation)
    )
    if denominator == 0:
        return None
    return (
        sum(
            left_value * right_value
            for left_value, right_value in zip(left_deviation, right_deviation, strict=True)
        )
        / denominator
    )


def _signal_id(
    observation: DemandObservation, signal_type: str, direction: str, period_key: str
) -> str:
    source = ":".join(
        (observation.store_id, observation.product_id, signal_type, direction, period_key)
    )
    return f"signal-{sha256(source.encode()).hexdigest()[:16]}"
