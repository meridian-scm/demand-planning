"""Orchestration layer: reads the database, drives the pure engines, writes results.

This is the only place that knows about both SQLAlchemy sessions and the
forecasting/exception engines. Keeping the coupling here means the engines stay
pure and the API routers stay thin.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import InsufficientHistoryError, NotFoundError
from app.core.logging import get_logger
from app.db.base import utcnow
from app.models import (
    Forecast,
    ForecastRun,
    Insight,
    InventorySnapshot,
    PlanningException,
    Product,
    SalesHistory,
)
from app.models.enums import ExceptionSeverity, ExceptionStatus, ForecastModel, InsightScope
from app.services.ai import InsightService, Narrative
from app.services.exceptions import ExceptionDetector, InventoryPosition
from app.services.forecasting import ForecastEngine, ForecastResult, Observation

logger = get_logger(__name__)

_SEVERITY_ORDER = {
    ExceptionSeverity.CRITICAL.value: 0,
    ExceptionSeverity.HIGH.value: 1,
    ExceptionSeverity.MEDIUM.value: 2,
    ExceptionSeverity.LOW.value: 3,
}


# --------------------------------------------------------------------------- #
# Read helpers
# --------------------------------------------------------------------------- #
def get_product_or_404(db: Session, product_id: int) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise NotFoundError(f"Product {product_id} not found.", details={"product_id": product_id})
    return product


def load_observations(db: Session, product_id: int) -> list[Observation]:
    """Load a product's demand history as engine-ready observations."""
    rows = db.execute(
        select(SalesHistory.period_start, func.sum(SalesHistory.units_sold))
        .where(SalesHistory.product_id == product_id)
        .group_by(SalesHistory.period_start)
        .order_by(SalesHistory.period_start)
    ).all()
    return [Observation(period_start=row[0], units=float(row[1] or 0)) for row in rows]


def latest_inventory(db: Session, product_id: int) -> InventorySnapshot | None:
    """Most recent inventory snapshot across all locations for a product."""
    return db.execute(
        select(InventorySnapshot)
        .where(InventorySnapshot.product_id == product_id)
        .order_by(InventorySnapshot.snapshot_date.desc(), InventorySnapshot.id.desc())
        .limit(1)
    ).scalar_one_or_none()


def _inventory_position(
    snapshot: InventorySnapshot | None, product: Product
) -> InventoryPosition | None:
    if snapshot is None:
        return None
    return InventoryPosition(
        available_units=float(snapshot.available_units),
        lead_time_days=product.lead_time_days,
        safety_stock_units=float(product.safety_stock_units or 0),
        snapshot_date=snapshot.snapshot_date,
    )


# --------------------------------------------------------------------------- #
# Forecasting
# --------------------------------------------------------------------------- #
class PlanningService:
    """Runs forecast cycles and exception detection against the database."""

    def __init__(
        self,
        db: Session,
        *,
        engine: ForecastEngine | None = None,
        detector: ExceptionDetector | None = None,
        insights: InsightService | None = None,
    ) -> None:
        self.db = db
        self.engine = engine or ForecastEngine()
        self.detector = detector or ExceptionDetector()
        self.insights = insights or InsightService()

    # -- forecast runs --------------------------------------------------- #
    def run_forecast(
        self,
        *,
        horizon: int,
        model: str = ForecastModel.AUTO.value,
        product_ids: Sequence[int] | None = None,
        run_label: str | None = None,
        detect_exceptions: bool = True,
    ) -> ForecastRun:
        """Forecast every requested product and persist the results as one run.

        Products with too little history are skipped rather than failing the
        whole run — a planning cycle must still complete when a handful of new
        SKUs are not yet forecastable.
        """
        products = self._resolve_products(product_ids)
        if not products:
            raise NotFoundError("No active products matched the request.")

        run = ForecastRun(
            run_label=run_label or f"Cycle {utcnow():%Y-%m-%d %H:%M}",
            requested_model=model,
            horizon_periods=horizon,
        )
        self.db.add(run)
        self.db.flush()

        skipped: list[dict] = []
        forecasted = 0

        for product in products:
            observations = load_observations(self.db, product.id)
            try:
                result = self.engine.forecast(observations, horizon=horizon, model=model)
            except InsufficientHistoryError as exc:
                skipped.append({"product_id": product.id, "sku": product.sku, "reason": exc.message})
                continue

            self._persist_forecast(run, product, result)
            forecasted += 1

            if detect_exceptions:
                self._refresh_exceptions(product, observations, result)

        run.products_forecasted = forecasted
        run.products_skipped = len(skipped)
        run.completed_at = utcnow()
        run.notes = {"skipped": skipped} if skipped else None

        self.db.commit()
        self.db.refresh(run)
        logger.info(
            "forecast run %s complete: %s forecast, %s skipped", run.id, forecasted, len(skipped)
        )
        return run

    def forecast_product(
        self,
        product_id: int,
        *,
        horizon: int,
        model: str = ForecastModel.AUTO.value,
        persist: bool = False,
    ) -> tuple[Product, ForecastResult]:
        """Forecast a single product, optionally persisting it as a one-SKU run."""
        product = get_product_or_404(self.db, product_id)
        observations = load_observations(self.db, product_id)
        result = self.engine.forecast(observations, horizon=horizon, model=model)

        if persist:
            run = ForecastRun(
                run_label=f"{product.sku} ad-hoc {utcnow():%Y-%m-%d %H:%M}",
                requested_model=model,
                horizon_periods=horizon,
                products_forecasted=1,
                completed_at=utcnow(),
            )
            self.db.add(run)
            self.db.flush()
            self._persist_forecast(run, product, result)
            self.db.commit()

        return product, result

    def _resolve_products(self, product_ids: Sequence[int] | None) -> list[Product]:
        statement = select(Product).where(Product.active.is_(True))
        if product_ids:
            statement = statement.where(Product.id.in_(list(product_ids)))
        return list(self.db.execute(statement.order_by(Product.sku)).scalars())

    def _persist_forecast(self, run: ForecastRun, product: Product, result: ForecastResult) -> None:
        for point in result.points:
            self.db.add(
                Forecast(
                    run_id=run.id,
                    product_id=product.id,
                    period_start=point.period_start,
                    forecast_units=point.forecast_units,
                    lower_bound_units=point.lower_bound_units,
                    upper_bound_units=point.upper_bound_units,
                    model_used=result.model_used,
                    mape=result.metrics.mape,
                    wape=result.metrics.wape,
                    rmse=result.metrics.rmse,
                    confidence_level=result.confidence_level,
                    model_params={
                        **{k: v for k, v in result.params.items() if isinstance(v, int | float | str)},
                        "history_periods": result.history_periods,
                        "candidates": result.candidates_evaluated,
                    },
                )
            )

    # -- exceptions ------------------------------------------------------ #
    def _refresh_exceptions(
        self,
        product: Product,
        observations: list[Observation],
        result: ForecastResult | None,
    ) -> None:
        """Replace this product's open exceptions with a freshly detected set.

        Open exceptions are regenerated each cycle so the queue reflects the
        current picture. Anything a planner has acknowledged, resolved or
        dismissed is left untouched — that decision is theirs to keep.
        """
        snapshot = latest_inventory(self.db, product.id)
        detected = self.detector.detect(
            product_name=product.name,
            observations=observations,
            forecast=result,
            inventory=_inventory_position(snapshot, product),
        )

        existing_open = self.db.execute(
            select(PlanningException).where(
                PlanningException.product_id == product.id,
                PlanningException.status == ExceptionStatus.OPEN.value,
            )
        ).scalars()
        for row in existing_open:
            self.db.delete(row)
        self.db.flush()

        for item in detected:
            self.db.add(
                PlanningException(
                    product_id=product.id,
                    exception_type=item.exception_type,
                    severity=item.severity,
                    status=ExceptionStatus.OPEN.value,
                    detected_for_period=item.detected_for_period,
                    title=item.title,
                    message=item.message,
                    recommendation=item.recommendation,
                    metric_value=item.metric_value,
                    baseline_value=item.baseline_value,
                    deviation_pct=item.deviation_pct,
                    context=item.context,
                )
            )

    def detect_exceptions_for_product(self, product_id: int) -> list[PlanningException]:
        """Re-run detection for one product against its latest stored forecast."""
        product = get_product_or_404(self.db, product_id)
        observations = load_observations(self.db, product_id)

        result: ForecastResult | None = None
        try:
            result = self.engine.forecast(
                observations, horizon=self.engine.holdout_periods or 3, model=ForecastModel.AUTO.value
            )
        except InsufficientHistoryError:
            logger.debug("product %s has too little history to forecast", product_id)

        self._refresh_exceptions(product, observations, result)
        self.db.commit()

        return list(
            self.db.execute(
                select(PlanningException)
                .where(
                    PlanningException.product_id == product_id,
                    PlanningException.status == ExceptionStatus.OPEN.value,
                )
                .order_by(PlanningException.severity)
            ).scalars()
        )

    def update_exception_status(self, exception_id: int, status: str) -> PlanningException:
        row = self.db.get(PlanningException, exception_id)
        if row is None:
            raise NotFoundError(
                f"Exception {exception_id} not found.", details={"exception_id": exception_id}
            )
        row.status = status
        self.db.commit()
        self.db.refresh(row)
        return row

    # -- insights -------------------------------------------------------- #
    def generate_product_insight(self, product_id: int, *, persist: bool = True) -> Insight:
        """Build an AI narrative for one product from its history and forecast."""
        product = get_product_or_404(self.db, product_id)
        observations = load_observations(self.db, product_id)

        latest_run_id = self.db.execute(
            select(func.max(Forecast.run_id)).where(Forecast.product_id == product_id)
        ).scalar()
        forecast_rows = (
            list(
                self.db.execute(
                    select(Forecast)
                    .where(Forecast.product_id == product_id, Forecast.run_id == latest_run_id)
                    .order_by(Forecast.period_start)
                ).scalars()
            )
            if latest_run_id
            else []
        )

        open_exceptions = list(
            self.db.execute(
                select(PlanningException).where(
                    PlanningException.product_id == product_id,
                    PlanningException.status == ExceptionStatus.OPEN.value,
                )
            ).scalars()
        )

        history_units = [item.units for item in observations]
        context = {
            "scope": InsightScope.PRODUCT.value,
            "product_name": product.name,
            "sku": product.sku,
            "category": product.category,
            "history_periods": len(history_units),
            "history_total_units": sum(history_units),
            "recent_history": [
                {"period": str(item.period_start), "units": item.units} for item in observations[-12:]
            ],
            "forecast_total_units": sum(float(row.forecast_units) for row in forecast_rows),
            "horizon_periods": len(forecast_rows),
            "model_used": forecast_rows[0].model_used if forecast_rows else None,
            "wape": forecast_rows[0].wape if forecast_rows else None,
            "growth_pct": _growth_pct(history_units),
            "exceptions": [
                {
                    "type": row.exception_type,
                    "severity": row.severity,
                    "title": row.title,
                    "recommendation": row.recommendation,
                }
                for row in open_exceptions
            ],
        }

        narrative = self.insights.generate(context)
        return self._store_insight(
            narrative, scope=InsightScope.PRODUCT.value, product_id=product_id, context=context, persist=persist
        )

    def generate_portfolio_insight(self, *, persist: bool = True) -> Insight:
        """Build an AI narrative summarising the whole planning position."""
        from app.services.analytics import AnalyticsService  # local import avoids a cycle

        analytics = AnalyticsService(self.db)
        summary = analytics.dashboard_summary()
        trends = analytics.demand_trends(limit=5)

        context = {
            "scope": InsightScope.PORTFOLIO.value,
            "product_count": summary["active_products"],
            "history_total_units": summary["history_total_units"],
            "forecast_total_units": summary["forecast_total_units"],
            "growth_pct": summary["demand_growth_pct"],
            "open_exception_count": summary["open_exceptions"],
            "critical_exception_count": summary["critical_exceptions"],
            "top_growing": [item["name"] for item in trends["growing"]],
            "top_declining": [item["name"] for item in trends["declining"]],
        }

        narrative = self.insights.generate(context)
        return self._store_insight(
            narrative, scope=InsightScope.PORTFOLIO.value, product_id=None, context=context, persist=persist
        )

    def _store_insight(
        self,
        narrative: Narrative,
        *,
        scope: str,
        product_id: int | None,
        context: dict,
        persist: bool,
    ) -> Insight:
        insight = Insight(
            scope=scope,
            product_id=product_id,
            headline=narrative.headline,
            summary=narrative.summary,
            recommendations=narrative.recommendations,
            generated_by=narrative.generated_by,
            model_name=narrative.model_name,
            context=context,
        )
        if persist:
            self.db.add(insight)
            self.db.commit()
            self.db.refresh(insight)
        return insight


def _growth_pct(values: list[float]) -> float | None:
    """Period-over-period growth of the recent half of a series versus the prior half."""
    if len(values) < 4:
        return None
    half = len(values) // 2
    earlier = sum(values[:half])
    later = sum(values[half:])
    if earlier == 0:
        return None
    return round((later - earlier) / earlier * 100.0, 2)


def severity_rank(severity: str) -> int:
    """Sort key placing the most urgent severities first."""
    return _SEVERITY_ORDER.get(severity, 99)
