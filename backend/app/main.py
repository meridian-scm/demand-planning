"""FastAPI application factory and process entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.router import create_api_router
from app.application.forecast_preview import ForecastPreviewService
from app.application.forecasting import ForecastingEngine
from app.application.inventory_risk import InventoryRiskService
from app.application.overview import OverviewService
from app.application.planning_exceptions import PlanningExceptionService
from app.application.readiness import ReadinessService
from app.application.signals import SignalDetectionService
from app.config import Settings, get_settings
from app.infrastructure.duckdb import (
    DuckDBForecastRunRepository,
    DuckDBOverviewRepository,
    DuckDBPlanningRepository,
)
from app.infrastructure.forecasting import build_candidate_models
from app.ports.repositories.forecast_runs import ForecastRunReadRepository
from app.ports.repositories.overview import OverviewReadRepository
from app.ports.repositories.planning import PlanningReadRepository


def create_app(
    settings: Settings | None = None,
    repository: PlanningReadRepository | None = None,
    forecast_repository: ForecastRunReadRepository | None = None,
    overview_repository: OverviewReadRepository | None = None,
) -> FastAPI:
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
    planning_repository = repository or DuckDBPlanningRepository(
        runtime_settings.artifact_version_directory
    )
    readiness_service = ReadinessService(
        runtime_settings.artifact_version_directory, planning_repository
    )
    forecasting_engine = ForecastingEngine(build_candidate_models)
    preview_service = ForecastPreviewService(
        planning_repository,
        forecasting_engine,
        maximum_horizon=runtime_settings.preview_max_horizon_months,
    )
    signal_service = SignalDetectionService(planning_repository)
    inventory_risk_service = InventoryRiskService(planning_repository, forecasting_engine)
    planning_exception_service = PlanningExceptionService(
        inventory_risk_service,
        signal_service,
        preview_service,
    )
    forecast_run_repository = forecast_repository or DuckDBForecastRunRepository(
        runtime_settings.forecast_run_directory
    )
    portfolio_repository = overview_repository or DuckDBOverviewRepository(
        runtime_settings.artifact_version_directory,
        runtime_settings.forecast_run_directory,
    )
    overview_service = OverviewService(forecast_run_repository, portfolio_repository)
    application.include_router(
        create_api_router(
            readiness_service,
            planning_repository,
            preview_service,
            signal_service,
            inventory_risk_service,
            planning_exception_service,
            forecast_run_repository,
            overview_service,
        )
    )
    return application


app = create_app()
