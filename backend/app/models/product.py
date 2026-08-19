"""Product master data."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.forecast import Forecast
    from app.models.inventory import InventorySnapshot
    from app.models.planning_exception import PlanningException
    from app.models.sales import SalesHistory


class Product(Base, TimestampMixin):
    """A stock-keeping unit that demand is planned for."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    subcategory: Mapped[str | None] = mapped_column(String(128))
    unit_of_measure: Mapped[str] = mapped_column(String(16), default="EA", nullable=False)
    unit_cost: Mapped[float | None] = mapped_column(Numeric(12, 2))
    unit_price: Mapped[float | None] = mapped_column(Numeric(12, 2))
    # Replenishment parameters that drive stockout / excess detection.
    lead_time_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    safety_stock_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reorder_point_units: Mapped[int | None] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(default=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    sales_history: Mapped[list[SalesHistory]] = relationship(
        back_populates="product", cascade="all, delete-orphan", passive_deletes=True
    )
    inventory_snapshots: Mapped[list[InventorySnapshot]] = relationship(
        back_populates="product", cascade="all, delete-orphan", passive_deletes=True
    )
    forecasts: Mapped[list[Forecast]] = relationship(
        back_populates="product", cascade="all, delete-orphan", passive_deletes=True
    )
    exceptions: Mapped[list[PlanningException]] = relationship(
        back_populates="product", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Product {self.sku} {self.name!r}>"
