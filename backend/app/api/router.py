"""Composition root for API routers."""

from fastapi import APIRouter

from app.api.routes.operations import create_operations_router
from app.api.v1.router import router as v1_router
from app.application.readiness import ReadinessService


def create_api_router(readiness_service: ReadinessService) -> APIRouter:
    """Compose operational and versioned endpoint groups."""

    router = APIRouter()
    router.include_router(create_operations_router(readiness_service))
    router.include_router(v1_router)
    return router
