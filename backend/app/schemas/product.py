"""Product master-data schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel


class ProductBase(BaseModel):
    sku: str = Field(min_length=1, max_length=64, examples=["SKU-1001"])
    name: str = Field(min_length=1, max_length=255)
    category: str = Field(min_length=1, max_length=128)
    subcategory: str | None = Field(default=None, max_length=128)
    unit_of_measure: str = Field(default="EA", max_length=16)
    unit_cost: float | None = Field(default=None, ge=0)
    unit_price: float | None = Field(default=None, ge=0)
    lead_time_days: int = Field(default=30, ge=0, le=365)
    safety_stock_units: int = Field(default=0, ge=0)
    reorder_point_units: int | None = Field(default=None, ge=0)
    active: bool = True
    description: str | None = None

    @field_validator("sku")
    @classmethod
    def _upper_sku(cls, value: str) -> str:
        """SKUs are matched case-insensitively everywhere, so store them upper."""
        return value.strip().upper()


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    """Partial update - every field is optional."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    category: str | None = Field(default=None, min_length=1, max_length=128)
    subcategory: str | None = None
    unit_of_measure: str | None = None
    unit_cost: float | None = Field(default=None, ge=0)
    unit_price: float | None = Field(default=None, ge=0)
    lead_time_days: int | None = Field(default=None, ge=0, le=365)
    safety_stock_units: int | None = Field(default=None, ge=0)
    reorder_point_units: int | None = Field(default=None, ge=0)
    active: bool | None = None
    description: str | None = None


class ProductRead(ORMModel, ProductBase):
    id: int
    created_at: datetime
    updated_at: datetime
