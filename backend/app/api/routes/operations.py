"""Process liveness and reference-data readiness endpoints."""

from fastapi import APIRouter, Response, status

from app import __version__
from app.application.readiness import ReadinessService
from app.schemas.operations import HealthResponse, ReadinessResponse


def create_operations_router(readiness_service: ReadinessService) -> APIRouter:
    """Build operational routes with explicit application-service dependencies."""

    router = APIRouter(prefix="/api", tags=["operations"])

    @router.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(service="meridian-backend", version=__version__)

    @router.get("/ready", response_model=ReadinessResponse)
    def ready(response: Response) -> ReadinessResponse:
        result = readiness_service.check()
        if not result.data_ready:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(
            status="ready" if result.data_ready else "not_ready",
            data_ready=result.data_ready,
            checks=result.checks,
            detail=result.detail,
        )

    return router
