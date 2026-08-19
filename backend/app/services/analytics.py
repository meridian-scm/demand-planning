"""Aggregations that power the dashboard.

All of these are read-only and pushed into SQL where practical, so the API
stays responsive as history grows.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import Float, case, cast, func, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models import Forecast, PlanningException, Product, SalesHistory
from app.models.enums import ExceptionSeverity, ExceptionStatus

#: How many trailing periods count as "recent" for growth comparisons.
RECENT_WINDOW = 3


class AnalyticsService:
    """Dashboard-level queries over demand, forecasts and exceptions."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------ #
    # Headline KPIs
    # ------------------------------------------------------------------ #
    def dashboard_summary(self) -> dict:
        """The KPI tiles at the top of the dashboard."""
        active_products = (
            self.db.execute(
                select(func.count(Product.id)).where(Product.active.is_(True))
            ).scalar()
            or 0
        )

        history_total = (
            self.db.execute(select(func.coalesce(func.sum(SalesHistory.units_sold), 0))).scalar() or 0
        )

        latest_run_id = self.db.execute(select(func.max(Forecast.run_id))).scalar()
        forecast_total = 0.0
        forecast_periods = 0
        if latest_run_id is not None:
            forecast_total = float(
                self.db.execute(
                    select(func.coalesce(func.sum(Forecast.forecast_units), 0.0)).where(
                        Forecast.run_id == latest_run_id
                    )
                ).scalar()
                or 0.0
            )
            forecast_periods = (
                self.db.execute(
                    select(func.count(func.distinct(Forecast.period_start))).where(
                        Forecast.run_id == latest_run_id
                    )
                ).scalar()
                or 0
            )

        open_exceptions = (
            self.db.execute(
                select(func.count(PlanningException.id)).where(
                    PlanningException.status == ExceptionStatus.OPEN.value
                )
            ).scalar()
            or 0
        )
        critical_exceptions = (
            self.db.execute(
                select(func.count(PlanningException.id)).where(
                    PlanningException.status == ExceptionStatus.OPEN.value,
                    PlanningException.severity == ExceptionSeverity.CRITICAL.value,
                )
            ).scalar()
            or 0
        )

        accuracy = None
        if latest_run_id is not None:
            accuracy = self.db.execute(
                select(func.avg(Forecast.wape)).where(
                    Forecast.run_id == latest_run_id, Forecast.wape.isnot(None)
                )
            ).scalar()

        return {
            "active_products": int(active_products),
            "history_total_units": float(history_total),
            "forecast_total_units": round(forecast_total, 2),
            "forecast_periods": int(forecast_periods),
            "demand_growth_pct": self.portfolio_growth_pct(),
            "open_exceptions": int(open_exceptions),
            "critical_exceptions": int(critical_exceptions),
            "average_wape": round(float(accuracy), 2) if accuracy is not None else None,
            "latest_run_id": latest_run_id,
        }

    def portfolio_growth_pct(self) -> float | None:
        """Growth of the most recent window against the window before it."""
        periods = [
            row[0]
            for row in self.db.execute(
                select(SalesHistory.period_start)
                .group_by(SalesHistory.period_start)
                .order_by(SalesHistory.period_start.desc())
                .limit(RECENT_WINDOW * 2)
            ).all()
        ]
        if len(periods) < RECENT_WINDOW * 2:
            return None

        recent, prior = periods[:RECENT_WINDOW], periods[RECENT_WINDOW:]
        recent_total = self._units_in(recent)
        prior_total = self._units_in(prior)
        if prior_total == 0:
            return None
        return round((recent_total - prior_total) / prior_total * 100.0, 2)

    def _units_in(self, periods: list[date]) -> float:
        return float(
            self.db.execute(
                select(func.coalesce(func.sum(SalesHistory.units_sold), 0)).where(
                    SalesHistory.period_start.in_(periods)
                )
            ).scalar()
            or 0
        )

    # ------------------------------------------------------------------ #
    # Series for charts
    # ------------------------------------------------------------------ #
    def demand_timeline(self, *, product_id: int | None = None) -> dict:
        """Actuals and the latest forecast on one continuous monthly timeline."""
        history_statement = select(
            SalesHistory.period_start, func.sum(SalesHistory.units_sold)
        ).group_by(SalesHistory.period_start)
        if product_id is not None:
            history_statement = history_statement.where(SalesHistory.product_id == product_id)

        history = [
            {"period_start": row[0], "units": float(row[1] or 0)}
            for row in self.db.execute(history_statement.order_by(SalesHistory.period_start)).all()
        ]

        latest_run_statement = select(func.max(Forecast.run_id))
        if product_id is not None:
            latest_run_statement = latest_run_statement.where(Forecast.product_id == product_id)
        latest_run_id = self.db.execute(latest_run_statement).scalar()

        forecast: list[dict] = []
        if latest_run_id is not None:
            statement = (
                select(
                    Forecast.period_start,
                    func.sum(Forecast.forecast_units),
                    func.sum(Forecast.lower_bound_units),
                    func.sum(Forecast.upper_bound_units),
                )
                .where(Forecast.run_id == latest_run_id)
                .group_by(Forecast.period_start)
                .order_by(Forecast.period_start)
            )
            if product_id is not None:
                statement = statement.where(Forecast.product_id == product_id)

            forecast = [
                {
                    "period_start": row[0],
                    "forecast_units": round(float(row[1] or 0), 2),
                    "lower_bound_units": round(float(row[2]), 2) if row[2] is not None else None,
                    "upper_bound_units": round(float(row[3]), 2) if row[3] is not None else None,
                }
                for row in self.db.execute(statement).all()
            ]

        return {"history": history, "forecast": forecast, "run_id": latest_run_id}

    def demand_trends(self, *, limit: int = 10) -> dict:
        """Products ranked by recent growth, split into growing and declining."""
        periods = [
            row[0]
            for row in self.db.execute(
                select(SalesHistory.period_start)
                .group_by(SalesHistory.period_start)
                .order_by(SalesHistory.period_start.desc())
                .limit(RECENT_WINDOW * 2)
            ).all()
        ]
        if len(periods) < RECENT_WINDOW * 2:
            return {"growing": [], "declining": [], "window_periods": RECENT_WINDOW}

        recent, prior = set(periods[:RECENT_WINDOW]), set(periods[RECENT_WINDOW:])

        rows = self.db.execute(
            select(
                Product.id,
                Product.sku,
                Product.name,
                Product.category,
                func.sum(
                    case((SalesHistory.period_start.in_(recent), SalesHistory.units_sold), else_=0)
                ).label("recent_units"),
                func.sum(
                    case((SalesHistory.period_start.in_(prior), SalesHistory.units_sold), else_=0)
                ).label("prior_units"),
            )
            .join(SalesHistory, SalesHistory.product_id == Product.id)
            .where(Product.active.is_(True))
            .group_by(Product.id, Product.sku, Product.name, Product.category)
        ).all()

        scored: list[dict] = []
        for row in rows:
            recent_units = float(row.recent_units or 0)
            prior_units = float(row.prior_units or 0)
            if prior_units == 0:
                continue
            growth = (recent_units - prior_units) / prior_units * 100.0
            scored.append(
                {
                    "product_id": row.id,
                    "sku": row.sku,
                    "name": row.name,
                    "category": row.category,
                    "recent_units": recent_units,
                    "prior_units": prior_units,
                    "growth_pct": round(growth, 2),
                }
            )

        scored.sort(key=lambda item: item["growth_pct"], reverse=True)
        growing = [item for item in scored if item["growth_pct"] > 0][:limit]
        declining = [item for item in scored if item["growth_pct"] < 0][-limit:]
        declining.sort(key=lambda item: item["growth_pct"])

        return {"growing": growing, "declining": declining, "window_periods": RECENT_WINDOW}

    def category_breakdown(self) -> list[dict]:
        """Demand and forecast totals grouped by product category."""
        latest_run_id = self.db.execute(select(func.max(Forecast.run_id))).scalar()

        history_rows = self.db.execute(
            select(Product.category, func.sum(SalesHistory.units_sold))
            .join(SalesHistory, SalesHistory.product_id == Product.id)
            .group_by(Product.category)
        ).all()
        history_by_category = {row[0]: float(row[1] or 0) for row in history_rows}

        forecast_by_category: dict[str, float] = {}
        if latest_run_id is not None:
            forecast_rows = self.db.execute(
                select(Product.category, func.sum(cast(Forecast.forecast_units, Float)))
                .join(Forecast, Forecast.product_id == Product.id)
                .where(Forecast.run_id == latest_run_id)
                .group_by(Product.category)
            ).all()
            forecast_by_category = {row[0]: float(row[1] or 0) for row in forecast_rows}

        categories = sorted(set(history_by_category) | set(forecast_by_category))
        return [
            {
                "category": category,
                "history_units": round(history_by_category.get(category, 0.0), 2),
                "forecast_units": round(forecast_by_category.get(category, 0.0), 2),
            }
            for category in categories
        ]

    def product_detail(self, product_id: int) -> dict:
        """Everything the product drill-down page needs, in one round trip."""
        product = self.db.get(Product, product_id)
        if product is None:
            raise NotFoundError(
                f"Product {product_id} not found.", details={"product_id": product_id}
            )

        timeline = self.demand_timeline(product_id=product_id)
        history_units = [item["units"] for item in timeline["history"]]

        exceptions = list(
            self.db.execute(
                select(PlanningException)
                .where(
                    PlanningException.product_id == product_id,
                    PlanningException.status == ExceptionStatus.OPEN.value,
                )
                .order_by(PlanningException.detected_for_period.desc())
            ).scalars()
        )

        latest_forecast = self.db.execute(
            select(Forecast)
            .where(Forecast.product_id == product_id, Forecast.run_id == timeline["run_id"])
            .order_by(Forecast.period_start)
            .limit(1)
        ).scalar_one_or_none()

        return {
            "product": product,
            "timeline": timeline,
            "exceptions": exceptions,
            "history_total_units": sum(history_units),
            "forecast_total_units": sum(
                item["forecast_units"] for item in timeline["forecast"]
            ),
            "model_used": latest_forecast.model_used if latest_forecast else None,
            "wape": latest_forecast.wape if latest_forecast else None,
            "mape": latest_forecast.mape if latest_forecast else None,
        }

    def exception_breakdown(self) -> list[dict]:
        """Open exception counts by type and severity, for the alerts panel."""
        rows = self.db.execute(
            select(
                PlanningException.exception_type,
                PlanningException.severity,
                func.count(PlanningException.id),
            )
            .where(PlanningException.status == ExceptionStatus.OPEN.value)
            .group_by(PlanningException.exception_type, PlanningException.severity)
        ).all()

        return [
            {"exception_type": row[0], "severity": row[1], "count": int(row[2])} for row in rows
        ]
