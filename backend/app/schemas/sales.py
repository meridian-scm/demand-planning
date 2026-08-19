"""Sales-history schemas."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel


class SalesCreate(BaseModel):
    product_id: int
    location_id: int | None = None
    period_start: date
    units_sold: int = Field(ge=0)
    revenue: float | None = Field(default=None, ge=0)
    channel: str | None = None
    source: str = "api"

    @field_validator("period_start")
    @classmethod
    def _first_of_month(cls, value: date) -> date:
        """The planning grain is monthly; snap any date to the 1st."""
        return date(value.year, value.month, 1)


class SalesBulkCreate(BaseModel):
    """Bulk upsert payload. Existing periods are overwritten, not duplicated."""

    records: list[SalesCreate] = Field(min_length=1, max_length=10000)


class SalesRead(ORMModel):
    id: int
    product_id: int
    location_id: int | None
    period_start: date
    units_sold: int
    revenue: float | None
    channel: str | None
    source: str
