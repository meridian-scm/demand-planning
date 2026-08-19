"""Planning-exception schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel

from app.models.enums import ExceptionStatus
from app.schemas.common import ORMModel


class ExceptionRead(ORMModel):
    id: int
    product_id: int
    exception_type: str
    severity: str
    status: str
    detected_for_period: date
    title: str
    message: str
    recommendation: str | None
    metric_value: float | None
    baseline_value: float | None
    deviation_pct: float | None
    context: dict | None
    created_at: datetime
    # Denormalised for the alerts table so the UI avoids an N+1 lookup.
    product_sku: str | None = None
    product_name: str | None = None


class ExceptionStatusUpdate(BaseModel):
    """Planner action on an exception."""

    status: ExceptionStatus
