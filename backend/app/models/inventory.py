"""Point-in-time inventory positions used for risk detection."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.location import Location
    from app.models.product import Product


class InventorySnapshot(Base, TimestampMixin):
    """On-hand / on-order position for a product at a point in time."""

    __tablename__ = "inventory_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "product_id", "location_id", "snapshot_date", name="uq_inventory_product_loc_date"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    location_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id", ondelete="SET NULL"), index=True
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    on_hand_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    on_order_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    allocated_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    product: Mapped[Product] = relationship(back_populates="inventory_snapshots")
    location: Mapped[Location | None] = relationship()

    @property
    def available_units(self) -> int:
        """Stock a planner can actually promise against."""
        return self.on_hand_units + self.on_order_units - self.allocated_units
