"""Planning exception detection.

Turns raw history, inventory positions and forecasts into the small set of
alerts a planner should actually act on. Every rule is pure and returns
:class:`DetectedException` value objects; persistence happens in the service
layer above so the rules stay unit-testable.

Rules implemented
-----------------
``demand_spike`` / ``demand_drop``
    Latest period deviates from the trailing baseline by more than a
    configurable percentage *and* by more than a z-score threshold. Requiring
    both keeps naturally noisy, low-volume SKUs from flooding the queue.
``stockout_risk``
    Available stock covers less than the configured number of forecast periods.
``excess_inventory``
    Available stock covers more than the configured number of forecast periods.
``forecast_anomaly``
    The chosen model's backtest error is worse than a usable threshold.
``new_product_volatility``
    Short history with a high coefficient of variation — forecast with care.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np

from app.core.config import settings
from app.models.enums import ExceptionSeverity, ExceptionType
from app.services.forecasting.types import ForecastResult, Observation

#: Backtest WAPE above which a forecast is flagged as unreliable.
UNRELIABLE_WAPE_PCT = 40.0
#: Coefficient of variation above which a short-history SKU is called volatile.
VOLATILE_CV = 0.5
#: History length (periods) below which a product counts as newly launched.
NEW_PRODUCT_PERIODS = 6


@dataclass(slots=True)
class DetectedException:
    """A single exception produced by a rule, ready to be persisted."""

    exception_type: str
    severity: str
    title: str
    message: str
    recommendation: str
    detected_for_period: date
    metric_value: float | None = None
    baseline_value: float | None = None
    deviation_pct: float | None = None
    context: dict = field(default_factory=dict)


@dataclass(slots=True)
class InventoryPosition:
    """Stock available to promise, plus the replenishment parameters."""

    available_units: float
    lead_time_days: int = 30
    safety_stock_units: float = 0.0
    snapshot_date: date | None = None


def _severity_from_deviation(deviation_pct: float) -> str:
    """Map a percentage deviation onto the planner-facing severity ladder."""
    magnitude = abs(deviation_pct)
    if magnitude >= 75:
        return ExceptionSeverity.CRITICAL.value
    if magnitude >= 50:
        return ExceptionSeverity.HIGH.value
    if magnitude >= 25:
        return ExceptionSeverity.MEDIUM.value
    return ExceptionSeverity.LOW.value


def _severity_from_cover(cover_periods: float, required: float) -> str:
    """Severity for stock-cover shortfalls: less cover means more urgency."""
    if required <= 0:
        return ExceptionSeverity.MEDIUM.value
    ratio = cover_periods / required
    if ratio <= 0.25:
        return ExceptionSeverity.CRITICAL.value
    if ratio <= 0.5:
        return ExceptionSeverity.HIGH.value
    if ratio <= 0.8:
        return ExceptionSeverity.MEDIUM.value
    return ExceptionSeverity.LOW.value


class ExceptionDetector:
    """Applies every detection rule to one product's planning picture."""

    def __init__(
        self,
        *,
        spike_threshold_pct: float | None = None,
        drop_threshold_pct: float | None = None,
        zscore_threshold: float | None = None,
        stockout_cover_periods: float | None = None,
        excess_cover_periods: float | None = None,
        baseline_window: int = 3,
    ) -> None:
        self.spike_threshold_pct = (
            spike_threshold_pct if spike_threshold_pct is not None else settings.spike_threshold_pct
        )
        self.drop_threshold_pct = (
            drop_threshold_pct if drop_threshold_pct is not None else settings.drop_threshold_pct
        )
        self.zscore_threshold = (
            zscore_threshold if zscore_threshold is not None else settings.zscore_threshold
        )
        self.stockout_cover_periods = (
            stockout_cover_periods
            if stockout_cover_periods is not None
            else settings.stockout_cover_periods
        )
        self.excess_cover_periods = (
            excess_cover_periods
            if excess_cover_periods is not None
            else settings.excess_cover_periods
        )
        self.baseline_window = baseline_window

    # ------------------------------------------------------------------ #
    # Entry point
    # ------------------------------------------------------------------ #
    def detect(
        self,
        *,
        product_name: str,
        observations: list[Observation],
        forecast: ForecastResult | None = None,
        inventory: InventoryPosition | None = None,
    ) -> list[DetectedException]:
        """Run every applicable rule and return the exceptions found."""
        found: list[DetectedException] = []
        ordered = sorted(observations, key=lambda item: item.period_start)

        found.extend(self._detect_demand_shift(product_name, ordered))
        found.extend(self._detect_volatility(product_name, ordered))

        if forecast is not None:
            found.extend(self._detect_forecast_anomaly(product_name, forecast, ordered))
            if inventory is not None:
                found.extend(self._detect_inventory_risk(product_name, forecast, inventory))

        return found

    # ------------------------------------------------------------------ #
    # Rules
    # ------------------------------------------------------------------ #
    def _detect_demand_shift(
        self, product_name: str, observations: list[Observation]
    ) -> list[DetectedException]:
        if len(observations) < self.baseline_window + 1:
            return []

        values = np.asarray([item.units for item in observations], dtype=float)
        latest = float(values[-1])
        latest_period = observations[-1].period_start

        baseline_slice = values[-(self.baseline_window + 1) : -1]
        baseline = float(baseline_slice.mean())
        if baseline == 0:
            return []

        deviation_pct = (latest - baseline) / baseline * 100.0

        # The z-score uses the full prior history so a genuinely erratic SKU
        # needs a bigger move before it is called an exception.
        prior = values[:-1]
        std = float(np.std(prior, ddof=1)) if prior.size > 1 else 0.0
        zscore = (latest - baseline) / std if std > 0 else 0.0

        context = {
            "latest_units": latest,
            "baseline_units": round(baseline, 2),
            "baseline_window": self.baseline_window,
            "zscore": round(zscore, 3),
        }

        if deviation_pct >= self.spike_threshold_pct and abs(zscore) >= self.zscore_threshold:
            return [
                DetectedException(
                    exception_type=ExceptionType.DEMAND_SPIKE.value,
                    severity=_severity_from_deviation(deviation_pct),
                    title=f"Demand spike on {product_name}",
                    message=(
                        f"Demand for {product_name} reached {latest:,.0f} units in "
                        f"{latest_period:%B %Y}, {deviation_pct:+.1f}% against a "
                        f"{self.baseline_window}-period baseline of {baseline:,.0f} units."
                    ),
                    recommendation=(
                        "Confirm whether the increase is a one-off event or a sustained shift, "
                        "then raise replenishment quantities and review supplier capacity for "
                        "the next planning cycle."
                    ),
                    detected_for_period=latest_period,
                    metric_value=latest,
                    baseline_value=round(baseline, 2),
                    deviation_pct=round(deviation_pct, 2),
                    context=context,
                )
            ]

        if -deviation_pct >= self.drop_threshold_pct and abs(zscore) >= self.zscore_threshold:
            return [
                DetectedException(
                    exception_type=ExceptionType.DEMAND_DROP.value,
                    severity=_severity_from_deviation(deviation_pct),
                    title=f"Demand decline on {product_name}",
                    message=(
                        f"Demand for {product_name} fell to {latest:,.0f} units in "
                        f"{latest_period:%B %Y}, {deviation_pct:+.1f}% against a "
                        f"{self.baseline_window}-period baseline of {baseline:,.0f} units."
                    ),
                    recommendation=(
                        "Check for lost customers, competitive pressure or a pull-forward in the "
                        "prior period, and reduce open replenishment to avoid building excess "
                        "inventory."
                    ),
                    detected_for_period=latest_period,
                    metric_value=latest,
                    baseline_value=round(baseline, 2),
                    deviation_pct=round(deviation_pct, 2),
                    context=context,
                )
            ]

        return []

    def _detect_inventory_risk(
        self,
        product_name: str,
        forecast: ForecastResult,
        inventory: InventoryPosition,
    ) -> list[DetectedException]:
        if not forecast.points:
            return []

        horizon_demand = [point.forecast_units for point in forecast.points]
        average_demand = float(np.mean(horizon_demand))
        if average_demand <= 0:
            return []

        net_available = inventory.available_units - inventory.safety_stock_units
        cover_periods = net_available / average_demand
        first_period = forecast.points[0].period_start

        context = {
            "available_units": inventory.available_units,
            "safety_stock_units": inventory.safety_stock_units,
            "average_forecast_units": round(average_demand, 2),
            "cover_periods": round(cover_periods, 2),
            "lead_time_days": inventory.lead_time_days,
        }

        if cover_periods < self.stockout_cover_periods:
            shortfall = max(0.0, forecast.points[0].forecast_units - net_available)
            return [
                DetectedException(
                    exception_type=ExceptionType.STOCKOUT_RISK.value,
                    severity=_severity_from_cover(cover_periods, self.stockout_cover_periods),
                    title=f"Stockout risk on {product_name}",
                    message=(
                        f"Available stock of {inventory.available_units:,.0f} units covers only "
                        f"{cover_periods:.1f} periods of forecast demand "
                        f"({average_demand:,.0f} units per period). Projected shortfall in "
                        f"{first_period:%B %Y} is {shortfall:,.0f} units."
                    ),
                    recommendation=(
                        f"Expedite replenishment now — the {inventory.lead_time_days}-day lead "
                        "time means an order placed later will not arrive before demand lands. "
                        "Consider partial allocation to priority customers."
                    ),
                    detected_for_period=first_period,
                    metric_value=round(cover_periods, 2),
                    baseline_value=self.stockout_cover_periods,
                    deviation_pct=round(
                        (cover_periods - self.stockout_cover_periods)
                        / self.stockout_cover_periods
                        * 100.0,
                        2,
                    )
                    if self.stockout_cover_periods
                    else None,
                    context={**context, "shortfall_units": round(shortfall, 2)},
                )
            ]

        if cover_periods > self.excess_cover_periods:
            excess_units = net_available - average_demand * self.excess_cover_periods
            return [
                DetectedException(
                    exception_type=ExceptionType.EXCESS_INVENTORY.value,
                    severity=_severity_from_deviation(
                        (cover_periods - self.excess_cover_periods)
                        / self.excess_cover_periods
                        * 100.0
                    ),
                    title=f"Excess inventory on {product_name}",
                    message=(
                        f"Available stock of {inventory.available_units:,.0f} units covers "
                        f"{cover_periods:.1f} periods against a target of "
                        f"{self.excess_cover_periods:.1f}. Roughly {excess_units:,.0f} units are "
                        "surplus to the planning horizon."
                    ),
                    recommendation=(
                        "Pause or reduce open purchase orders, and review whether the stock can "
                        "be redeployed to another location before it ages."
                    ),
                    detected_for_period=first_period,
                    metric_value=round(cover_periods, 2),
                    baseline_value=self.excess_cover_periods,
                    deviation_pct=round(
                        (cover_periods - self.excess_cover_periods)
                        / self.excess_cover_periods
                        * 100.0,
                        2,
                    ),
                    context={**context, "excess_units": round(excess_units, 2)},
                )
            ]

        return []

    def _detect_forecast_anomaly(
        self,
        product_name: str,
        forecast: ForecastResult,
        observations: list[Observation],
    ) -> list[DetectedException]:
        wape = forecast.metrics.wape
        if wape is None or wape <= UNRELIABLE_WAPE_PCT:
            return []

        period = forecast.points[0].period_start if forecast.points else observations[-1].period_start
        return [
            DetectedException(
                exception_type=ExceptionType.FORECAST_ANOMALY.value,
                severity=ExceptionSeverity.HIGH.value
                if wape > 2 * UNRELIABLE_WAPE_PCT
                else ExceptionSeverity.MEDIUM.value,
                title=f"Low forecast confidence on {product_name}",
                message=(
                    f"The best available model ({forecast.model_used}) backtests at "
                    f"{wape:.1f}% WAPE, above the {UNRELIABLE_WAPE_PCT:.0f}% reliability "
                    "threshold. The statistical forecast should not be used unadjusted."
                ),
                recommendation=(
                    "Apply planner judgement or a consensus override for this SKU, and check "
                    "whether promotions, price changes or data quality issues explain the "
                    "unstable history."
                ),
                detected_for_period=period,
                metric_value=round(wape, 2),
                baseline_value=UNRELIABLE_WAPE_PCT,
                deviation_pct=round((wape - UNRELIABLE_WAPE_PCT) / UNRELIABLE_WAPE_PCT * 100.0, 2),
                context={
                    "model_used": forecast.model_used,
                    "mape": forecast.metrics.mape,
                    "rmse": forecast.metrics.rmse,
                    "history_periods": forecast.history_periods,
                },
            )
        ]

    def _detect_volatility(
        self, product_name: str, observations: list[Observation]
    ) -> list[DetectedException]:
        if not (2 <= len(observations) <= NEW_PRODUCT_PERIODS):
            return []

        values = np.asarray([item.units for item in observations], dtype=float)
        mean = float(values.mean())
        if mean <= 0:
            return []
        cv = float(np.std(values, ddof=1)) / mean
        if cv <= VOLATILE_CV:
            return []

        return [
            DetectedException(
                exception_type=ExceptionType.NEW_PRODUCT_VOLATILITY.value,
                severity=ExceptionSeverity.MEDIUM.value,
                title=f"Volatile early demand on {product_name}",
                message=(
                    f"{product_name} has only {len(observations)} periods of history with a "
                    f"coefficient of variation of {cv:.2f}. Demand has not yet stabilised."
                ),
                recommendation=(
                    "Plan this SKU with a manual override or an analogue product until at least "
                    f"{NEW_PRODUCT_PERIODS + 1} periods of history are available."
                ),
                detected_for_period=observations[-1].period_start,
                metric_value=round(cv, 3),
                baseline_value=VOLATILE_CV,
                deviation_pct=round((cv - VOLATILE_CV) / VOLATILE_CV * 100.0, 2),
                context={"periods": len(observations), "mean_units": round(mean, 2)},
            )
        ]
