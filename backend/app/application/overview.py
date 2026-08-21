"""Portfolio Overview orchestration and explainable exception rules."""

from collections.abc import Iterable
from hashlib import sha256
from statistics import median

from app.domain import (
    OverviewException,
    OverviewRiskCounts,
    OverviewSeriesEvidence,
    PortfolioOverview,
)
from app.domain.overview import OverviewExceptionSeverity, OverviewExceptionType
from app.ports.repositories.forecast_runs import ForecastRunReadRepository
from app.ports.repositories.overview import OverviewReadRepository

EXCESS_COVERAGE_MONTHS = 6.0
BIAS_THRESHOLD = 0.15
UNCERTAINTY_THRESHOLD = 1.0


class OverviewUnavailableError(RuntimeError):
    """Raised when a requested published-run overview cannot be assembled."""


class OverviewService:
    """Assemble honest portfolio summaries from one immutable forecast run."""

    def __init__(
        self,
        forecast_runs: ForecastRunReadRepository,
        overview_repository: OverviewReadRepository,
    ) -> None:
        self._forecast_runs = forecast_runs
        self._overview_repository = overview_repository

    def get_overview(
        self,
        *,
        run_id: str | None,
        store_id: str | None,
        exception_limit: int,
    ) -> PortfolioOverview:
        selected_run = (
            self._forecast_runs.get_run(run_id)
            if run_id is not None
            else next(iter(self._forecast_runs.list_runs()), None)
        )
        if selected_run is None:
            raise OverviewUnavailableError("No verified forecast run is available.")

        timeline = self._overview_repository.get_timeline(selected_run.run_id, store_id=store_id)
        evidence = self._overview_repository.get_series_evidence(
            selected_run.run_id, store_id=store_id
        )
        if not evidence:
            raise OverviewUnavailableError("The selected run has no series for this store scope.")

        actual_points = [point for point in timeline if point.actual_units is not None]
        recent = sum(point.actual_units or 0 for point in actual_points[-12:])
        prior = sum(point.actual_units or 0 for point in actual_points[-24:-12])
        demand_change = (recent - prior) / prior if prior else None
        forecast_demand = sum(point.forecast_units or 0.0 for point in timeline)

        risk_counts = {name: 0 for name in ("stockout", "below_safety_stock", "healthy", "excess")}
        unavailable = 0
        exceptions: list[OverviewException] = []
        for item in evidence:
            classification = _risk_classification(item)
            if classification is None:
                unavailable += 1
            else:
                risk_counts[classification] += 1
                risk_exception = _risk_exception(item, classification)
                if risk_exception is not None:
                    exceptions.append(risk_exception)
            exceptions.extend(_reliability_exceptions(item))

        exceptions.sort(
            key=lambda item: (
                -item.priority_score,
                item.metric_value,
                item.store_name,
                item.sku,
                item.exception_type,
            )
        )
        store_name = evidence[0].store_name if store_id is not None else "All stores"
        return PortfolioOverview(
            run_id=selected_run.run_id,
            data_version=selected_run.data_version,
            training_cutoff=selected_run.training_cutoff,
            horizon_months=selected_run.horizon_months,
            store_id=store_id,
            store_name=store_name,
            series_count=len(evidence),
            recent_12_month_demand=recent,
            prior_12_month_demand=prior,
            demand_change=demand_change,
            forecast_horizon_demand=forecast_demand,
            median_series_wape=_median_defined(item.wape for item in evidence),
            median_series_mase=_median_defined(item.mase for item in evidence),
            median_absolute_bias=_median_defined(
                abs(item.bias) if item.bias is not None else None for item in evidence
            ),
            weighted_interval_coverage=_weighted_coverage(evidence),
            risk_counts=OverviewRiskCounts(
                stockout=risk_counts["stockout"],
                below_safety_stock=risk_counts["below_safety_stock"],
                healthy=risk_counts["healthy"],
                excess=risk_counts["excess"],
                unavailable=unavailable,
            ),
            timeline=timeline,
            priority_exceptions=tuple(exceptions[:exception_limit]),
        )


def _risk_classification(item: OverviewSeriesEvidence) -> str | None:
    if item.covered_lead_time_days != item.lead_time_days:
        return None
    projected = _projected_inventory(item)
    if projected < 0:
        return "stockout"
    if projected < item.safety_stock:
        return "below_safety_stock"
    coverage = _coverage_months(item, projected)
    if coverage is not None and coverage > EXCESS_COVERAGE_MONTHS:
        return "excess"
    return "healthy"


def _projected_inventory(item: OverviewSeriesEvidence) -> float:
    return (
        item.available_inventory
        + item.on_order_due_within_lead_time
        - item.forecast_demand_during_lead_time
    )


def _coverage_months(item: OverviewSeriesEvidence, projected: float) -> float | None:
    if item.average_monthly_forecast <= 0:
        return None
    return max(0.0, projected) / item.average_monthly_forecast


def _risk_exception(item: OverviewSeriesEvidence, classification: str) -> OverviewException | None:
    projected = _projected_inventory(item)
    if classification == "stockout":
        return _exception(
            item,
            "potential_stockout",
            "critical",
            100,
            "Potential stockout before replenishment",
            "Projected inventory falls below zero before replenishment arrives.",
            "projected_inventory_units",
            projected,
            0.0,
        )
    if classification == "below_safety_stock":
        return _exception(
            item,
            "below_safety_stock",
            "high",
            85,
            "Inventory projected below safety stock",
            "Projected inventory does not meet the Store + SKU safety-stock policy.",
            "projected_inventory_units",
            projected,
            float(item.safety_stock),
        )
    if classification == "excess":
        coverage = _coverage_months(item, projected)
        assert coverage is not None
        return _exception(
            item,
            "excess_inventory",
            "medium",
            60,
            "Excess inventory coverage",
            "Projected inventory exceeds the configured six-month coverage threshold.",
            "coverage_months",
            coverage,
            EXCESS_COVERAGE_MONTHS,
        )
    return None


def _reliability_exceptions(item: OverviewSeriesEvidence) -> tuple[OverviewException, ...]:
    exceptions: list[OverviewException] = []
    width_ratio = item.average_interval_width / max(item.average_monthly_forecast, 1.0)
    if width_ratio >= UNCERTAINTY_THRESHOLD:
        exceptions.append(
            _exception(
                item,
                "forecast_uncertainty",
                "high" if width_ratio >= 2 else "medium",
                70 if width_ratio >= 2 else 55,
                "Forecast uncertainty is high",
                "The published interval is wide relative to expected demand.",
                "average_interval_width_ratio",
                width_ratio,
                UNCERTAINTY_THRESHOLD,
            )
        )
    if item.bias is not None and abs(item.bias) >= BIAS_THRESHOLD:
        exceptions.append(
            _exception(
                item,
                "forecast_bias",
                "high" if abs(item.bias) >= 0.3 else "medium",
                68 if abs(item.bias) >= 0.3 else 52,
                "Significant forecast bias",
                "Rolling-origin validation shows systematic over- or under-forecasting.",
                "forecast_bias",
                item.bias,
                BIAS_THRESHOLD,
            )
        )
    return tuple(exceptions)


def _exception(
    item: OverviewSeriesEvidence,
    exception_type: OverviewExceptionType,
    severity: OverviewExceptionSeverity,
    priority_score: int,
    title: str,
    description: str,
    metric_name: str,
    metric_value: float,
    threshold_value: float,
) -> OverviewException:
    identity = f"{item.store_id}|{item.product_id}|{exception_type}"
    return OverviewException(
        exception_id=f"overview-{sha256(identity.encode()).hexdigest()[:16]}",
        store_id=item.store_id,
        store_name=item.store_name,
        product_id=item.product_id,
        sku=item.sku,
        product_name=item.product_name,
        category=item.category,
        exception_type=exception_type,
        severity=severity,
        priority_score=priority_score,
        title=title,
        description=description,
        metric_name=metric_name,
        metric_value=metric_value,
        threshold_value=threshold_value,
        selected_model=item.selected_model,
    )


def _median_defined(values: Iterable[float | None]) -> float | None:
    defined = [value for value in values if value is not None]
    return float(median(defined)) if defined else None


def _weighted_coverage(evidence: tuple[OverviewSeriesEvidence, ...]) -> float | None:
    usable = [
        item
        for item in evidence
        if item.interval_coverage is not None and item.validation_points is not None
    ]
    denominator = sum(item.validation_points or 0 for item in usable)
    if denominator == 0:
        return None
    return (
        sum((item.interval_coverage or 0.0) * (item.validation_points or 0) for item in usable)
        / denominator
    )
