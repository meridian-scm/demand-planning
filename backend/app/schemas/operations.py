"""Schemas for process health and data readiness."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """Liveness response for the backend process."""

    model_config = ConfigDict(frozen=True)

    status: Literal["ok"] = "ok"
    service: str
    version: str


class ReadinessResponse(BaseModel):
    """Honest readiness response for reference-data availability."""

    model_config = ConfigDict(frozen=True)

    status: Literal["ready", "not_ready"]
    data_ready: bool
    checks: dict[str, bool]
    detail: str
