"""Planning exceptions — the alerts a planner works through each cycle."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Date, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import ExceptionSeverity, ExceptionStatus

if TYPE_CHECKING:
    from app.models.product import Product


class PlanningException(Base, TimestampMixin):
    """A detected planning risk requiring planner attention."""

    __tablename__ = "planning_exceptions"
    __table_args__ = (
        Index("ix_exception_status_severity", "status", "severity"),
        Index("ix_exception_product_type", "product_id", "exception_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    exception_type: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(
        String(16), default=ExceptionSeverity.MEDIUM.value, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(16), default=ExceptionStatus.OPEN.value, nullable=False, index=True
    )
    detected_for_period: Mapped[date] = mapped_column(Date, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation: Mapped[str | None] = mapped_column(Text)
    # The numbers that triggered the rule, kept for explainability.
    metric_value: Mapped[float | None] = mapped_column(Float)
    baseline_value: Mapped[float | None] = mapped_column(Float)
    deviation_pct: Mapped[float | None] = mapped_column(Float)
    context: Mapped[dict | None] = mapped_column(JSON)

    product: Mapped[Product] = relationship(back_populates="exceptions")

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<PlanningException {self.exception_type} p={self.product_id}>"
