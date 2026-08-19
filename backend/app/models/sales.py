"""Historical demand actuals — the input the whole system is built on."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.location import Location
    from app.models.product import Product


class SalesHistory(Base, TimestampMixin):
    """One period of actual demand for a product (optionally at a location).

    ``period_start`` is normalised to the first day of the month; the grain of
    the whole application is monthly, which matches how demand planners run
    their cycle.
    """

    __tablename__ = "sales_history"
    __table_args__ = (
        UniqueConstraint(
            "product_id", "location_id", "period_start", name="uq_sales_product_location_period"
        ),
        Index("ix_sales_product_period", "product_id", "period_start"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    location_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id", ondelete="SET NULL"), index=True
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    units_sold: Mapped[int] = mapped_column(Integer, nullable=False)
    revenue: Mapped[float | None] = mapped_column(Numeric(14, 2))
    channel: Mapped[str | None] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(32), default="erp", nullable=False)

    product: Mapped[Product] = relationship(back_populates="sales_history")
    location: Mapped[Location | None] = relationship()

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<SalesHistory product={self.product_id} {self.period_start} {self.units_sold}u>"
