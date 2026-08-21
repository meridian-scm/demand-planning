"""Composition root for API routers."""

from fastapi import APIRouter

from app.api.routes.operations import create_operations_router
from app.api.v1.router import create_v1_router
from app.application.forecast_preview import ForecastPreviewService
from app.application.inventory_risk import InventoryRiskService
from app.application.overview import OverviewService
from app.application.planning_exceptions import PlanningExceptionService
from app.application.readiness import ReadinessService
from app.application.signals import SignalDetectionService
from app.ports.repositories.forecast_runs import ForecastRunReadRepository
from app.ports.repositories.planning import PlanningReadRepository


def create_api_router(
    readiness_service: ReadinessService,
    repository: PlanningReadRepository,
    preview_service: ForecastPreviewService,
    signal_service: SignalDetectionService,
    inventory_risk_service: InventoryRiskService,
    planning_exception_service: PlanningExceptionService,
    forecast_run_repository: ForecastRunReadRepository,
    overview_service: OverviewService,
) -> APIRouter:
    """Compose operational and versioned endpoint groups."""

    router = APIRouter()
    router.include_router(create_operations_router(readiness_service))
    router.include_router(
        create_v1_router(
            repository,
            preview_service,
            signal_service,
            inventory_risk_service,
            planning_exception_service,
            forecast_run_repository,
            overview_service,
        )
    )
    return router
