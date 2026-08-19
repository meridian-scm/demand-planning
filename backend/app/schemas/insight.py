"""AI insight schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import InsightScope
from app.schemas.common import ORMModel


class InsightRequest(BaseModel):
    """Request a fresh narrative."""

    scope: InsightScope = InsightScope.PORTFOLIO
    product_id: int | None = Field(
        default=None, description="Required when scope is 'product'"
    )
    persist: bool = True


class InsightRead(ORMModel):
    id: int
    scope: str
    product_id: int | None
    headline: str
    summary: str
    recommendations: list[str] | None
    generated_by: str
    model_name: str | None
    created_at: datetime
