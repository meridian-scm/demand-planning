"""Location master-data schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel


class LocationCreate(BaseModel):
    code: str = Field(min_length=1, max_length=32, examples=["DC-EAST"])
    name: str = Field(min_length=1, max_length=255)
    region: str = Field(min_length=1, max_length=128)
    country: str | None = Field(default=None, max_length=64)
    active: bool = True

    @field_validator("code")
    @classmethod
    def _upper_code(cls, value: str) -> str:
        return value.strip().upper()


class LocationRead(ORMModel):
    id: int
    code: str
    name: str
    region: str
    country: str | None
    active: bool
    created_at: datetime
