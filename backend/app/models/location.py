"""Distribution centres / plants that demand is planned at."""

from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Location(Base, TimestampMixin):
    """A physical node in the supply network."""

    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    region: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    country: Mapped[str | None] = mapped_column(String(64))
    active: Mapped[bool] = mapped_column(default=True, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Location {self.code}>"
