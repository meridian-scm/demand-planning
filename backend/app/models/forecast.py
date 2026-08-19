"""Forecast runs and the individual period-level predictions they produce."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, utcnow
from app.models.enums import ForecastModel

if TYPE_CHECKING:
    from app.models.product import Product


class ForecastRun(Base, TimestampMixin):
    """A single execution of the forecast engine over one or more products.

    Keeping runs as first-class rows makes forecasts reproducible and lets the
    UI show "as of" versions rather than silently overwriting history.
    """

    __tablename__ = "forecast_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_label: Mapped[str] = mapped_column(String(128), nullable=False)
    requested_model: Mapped[str] = mapped_column(
        String(32), default=ForecastModel.AUTO.value, nullable=False
    )
    horizon_periods: Mapped[int] = mapped_column(Integer, nullable=False)
    products_forecasted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    products_skipped: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[dict | None] = mapped_column(JSON)

    forecasts: Mapped[list[Forecast]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<ForecastRun {self.id} {self.run_label!r}>"


class Forecast(Base, TimestampMixin):
    """A predicted demand quantity for one product in one future period."""

    __tablename__ = "forecasts"
    __table_args__ = (
        UniqueConstraint("run_id", "product_id", "period_start", name="uq_forecast_run_prod_period"),
        Index("ix_forecast_product_period", "product_id", "period_start"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("forecast_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    forecast_units: Mapped[float] = mapped_column(Float, nullable=False)
    lower_bound_units: Mapped[float | None] = mapped_column(Float)
    upper_bound_units: Mapped[float | None] = mapped_column(Float)
    model_used: Mapped[str] = mapped_column(String(32), nullable=False)
    # Backtest accuracy of the winning model, so planners can judge trust.
    mape: Mapped[float | None] = mapped_column(Float)
    wape: Mapped[float | None] = mapped_column(Float)
    rmse: Mapped[float | None] = mapped_column(Float)
    confidence_level: Mapped[float] = mapped_column(Float, default=0.95, nullable=False)
    model_params: Mapped[dict | None] = mapped_column(JSON)

    run: Mapped[ForecastRun] = relationship(back_populates="forecasts")
    product: Mapped[Product] = relationship(back_populates="forecasts")

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Forecast p={self.product_id} {self.period_start} {self.forecast_units:.1f}>"
