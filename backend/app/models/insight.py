"""AI-generated narratives and recommendations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import InsightScope

if TYPE_CHECKING:
    from app.models.product import Product


class Insight(Base, TimestampMixin):
    """A business-friendly summary produced by the AI layer.

    ``generated_by`` records whether the text came from the LLM or from the
    deterministic fallback, so the UI can label it honestly.
    """

    __tablename__ = "insights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scope: Mapped[str] = mapped_column(
        String(32), default=InsightScope.PORTFOLIO.value, nullable=False, index=True
    )
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    headline: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    recommendations: Mapped[list | None] = mapped_column(JSON)
    generated_by: Mapped[str] = mapped_column(String(48), default="fallback", nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(64))
    context: Mapped[dict | None] = mapped_column(JSON)

    product: Mapped[Product | None] = relationship()

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Insight {self.scope} {self.headline!r}>"
