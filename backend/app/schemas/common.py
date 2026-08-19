"""Shared schema building blocks."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ORMModel(BaseModel):
    """Base for schemas read directly from SQLAlchemy rows."""

    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    """A single page of results plus the paging metadata the UI needs."""

    items: list[T]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.items) < self.total


class StatusResponse(BaseModel):
    """Generic acknowledgement payload."""

    status: str
    message: str | None = None


class HealthResponse(BaseModel):
    """Liveness / readiness output."""

    status: str
    version: str
    environment: str
    database: str
    ai_provider: str
