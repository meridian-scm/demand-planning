"""FastAPI application factory and process entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.router import create_api_router
from app.application.readiness import ReadinessService
from app.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create an application with explicit, testable dependencies."""

    runtime_settings = settings or get_settings()
    application = FastAPI(
        title="Meridian Demand Planning API",
        summary="Statistical demand-planning API",
        version=__version__,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=runtime_settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    readiness_service = ReadinessService(runtime_settings.artifact_directory)
    application.include_router(create_api_router(readiness_service))
    return application


app = create_app()
