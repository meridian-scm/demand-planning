"""Composition root for versioned API routes."""

from fastapi import APIRouter

from app.api.v1.forecast_runs import create_forecast_run_router
from app.api.v1.overview import create_overview_router
from app.api.v1.planning import create_planning_router
from app.application.forecast_preview import ForecastPreviewService
from app.application.inventory_risk import InventoryRiskService
from app.application.overview import OverviewService
from app.application.planning_exceptions import PlanningExceptionService
from app.application.signals import SignalDetectionService
from app.ports.repositories.forecast_runs import ForecastRunReadRepository
from app.ports.repositories.planning import PlanningReadRepository


def create_v1_router(
    repository: PlanningReadRepository,
    preview_service: ForecastPreviewService,
    signal_service: SignalDetectionService,
    inventory_risk_service: InventoryRiskService,
    planning_exception_service: PlanningExceptionService,
    forecast_run_repository: ForecastRunReadRepository,
    overview_service: OverviewService,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1")
    router.include_router(
        create_planning_router(
            repository,
            preview_service,
            signal_service,
            inventory_risk_service,
            planning_exception_service,
        )
    )
    router.include_router(create_forecast_run_router(forecast_run_repository))
    router.include_router(create_overview_router(overview_service))
    return router
