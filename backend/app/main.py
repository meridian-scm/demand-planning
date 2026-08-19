"""FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.db.session import engine

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    logger.info("starting %s (%s)", settings.app_name, settings.environment)
    yield
    logger.info("shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description=(
            "AI-powered demand forecasting, trend analysis, exception detection "
            "and planning recommendations for supply chain teams."
        ),
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/api/health", tags=["health"])
    def health() -> dict:
        database_status = "up"
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception as exc:  # noqa: BLE001 - health check reports, never raises
            logger.warning("database health check failed: %s", exc)
            database_status = "down"

        if not settings.ai_enabled:
            ai_provider = "disabled"
        elif settings.ai_provider == "groq":
            ai_provider = f"groq:{settings.groq_model}"
        else:
            ai_provider = f"ollama:{settings.ollama_model}"

        return {
            "status": "ok" if database_status == "up" else "degraded",
            "version": app.version,
            "environment": settings.environment,
            "database": database_status,
            "ai_provider": ai_provider,
        }

    return app


app = create_app()
