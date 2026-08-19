"""Inventory-position schemas."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, computed_field

from app.schemas.common import ORMModel


class InventoryUpsert(BaseModel):
    product_id: int
    location_id: int | None = None
    snapshot_date: date
    on_hand_units: int = Field(default=0, ge=0)
    on_order_units: int = Field(default=0, ge=0)
    allocated_units: int = Field(default=0, ge=0)


class InventoryRead(ORMModel):
    id: int
    product_id: int
    location_id: int | None
    snapshot_date: date
    on_hand_units: int
    on_order_units: int
    allocated_units: int

    @computed_field
    @property
    def available_units(self) -> int:
        """Stock a planner can promise against."""
        return self.on_hand_units + self.on_order_units - self.allocated_units
