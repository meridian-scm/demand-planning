"""Domain exceptions and the handlers that translate them into HTTP responses."""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)


class DomainError(Exception):
    """Base class for expected, business-level failures."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "domain_error"

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ValidationError(DomainError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "validation_error"


class InsufficientHistoryError(DomainError):
    """Raised when a series is too short to produce a defensible forecast."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "insufficient_history"


class ConflictError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


class UpstreamServiceError(DomainError):
    """The AI provider (or another upstream dependency) failed."""

    status_code = status.HTTP_502_BAD_GATEWAY
    code = "upstream_unavailable"


def register_exception_handlers(app: FastAPI) -> None:
    """Attach the domain-error handler to the FastAPI application."""

    @app.exception_handler(DomainError)
    async def _handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
        logger.info("domain error: %s (%s)", exc.message, exc.code)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )
