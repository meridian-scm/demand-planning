"""Planner-facing catalog and historical-demand endpoints."""

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.application.demand_explorer import DemandExplorerService, PlanningDataNotFoundError
from app.application.forecast_preview import ForecastPreviewLimitError, ForecastPreviewService
from app.application.forecasting import ForecastingFailedError, InsufficientHistoryError
from app.application.inventory_risk import InventoryRiskService, InventoryRiskUnavailableError
from app.application.planning_exceptions import PlanningExceptionService
from app.application.signals import SignalDetectionService
from app.domain.exceptions import ExceptionSeverity, ExceptionStatus, ExceptionType
from app.ports.repositories.planning import PlanningReadRepository
from app.schemas.planning import (
    DemandPointResponse,
    DemandSeriesResponse,
    DemandSignalResponse,
    DemandSummaryResponse,
    ForecastMetricsResponse,
    ForecastPointResponse,
    ForecastPreviewRequest,
    ForecastPreviewResponse,
    InventoryPositionResponse,
    InventoryRiskResponse,
    ModelEvaluationResponse,
    PlanningExceptionResponse,
    PlanningPolicyResponse,
    ProductResponse,
    StoreResponse,
)


def create_planning_router(
    repository: PlanningReadRepository,
    preview_service: ForecastPreviewService,
    signal_service: SignalDetectionService,
    inventory_risk_service: InventoryRiskService,
    planning_exception_service: PlanningExceptionService,
) -> APIRouter:
    """Build read-only planning endpoints with an injected repository port."""

    router = APIRouter()
    demand_service = DemandExplorerService(repository)

    @router.get("/stores", response_model=list[StoreResponse], tags=["catalog"])
    def list_stores() -> list[StoreResponse]:
        return [StoreResponse(**asdict(store)) for store in repository.list_stores()]

    @router.get("/products", response_model=list[ProductResponse], tags=["catalog"])
    def search_products(
        store_id: str = Query(min_length=1),
        query: str = Query(default="", max_length=100),
        limit: int = Query(default=50, ge=1, le=100),
    ) -> list[ProductResponse]:
        products = repository.search_products(store_id, query.strip(), limit=limit)
        return [ProductResponse(**asdict(product)) for product in products]

    @router.get("/demand/series", response_model=DemandSeriesResponse, tags=["demand"])
    def get_demand_series(
        store_id: str = Query(min_length=1), product_id: str = Query(min_length=1)
    ) -> DemandSeriesResponse:
        try:
            series = demand_service.get_series(store_id, product_id)
        except PlanningDataNotFoundError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(error),
            ) from error
        return DemandSeriesResponse(
            store_id=store_id,
            product=ProductResponse(**asdict(series.product)),
            policy=PlanningPolicyResponse(
                lead_time_days=series.policy.lead_time_days,
                safety_stock=series.policy.safety_stock,
                reorder_point=series.policy.reorder_point,
                minimum_order_quantity=series.policy.minimum_order_quantity,
                order_multiple=series.policy.order_multiple,
                service_level_target=series.policy.service_level_target,
            ),
            observations=[
                DemandPointResponse(
                    period_start=observation.period_start,
                    demand_units=observation.demand_units,
                )
                for observation in series.observations
            ],
            summary=DemandSummaryResponse(**asdict(series.summary)),
        )

    @router.get("/signals", response_model=list[DemandSignalResponse], tags=["signals"])
    def get_signals(
        store_id: str = Query(min_length=1), product_id: str = Query(min_length=1)
    ) -> list[DemandSignalResponse]:
        try:
            signals = signal_service.get_signals(store_id, product_id)
        except PlanningDataNotFoundError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(error),
            ) from error
        return [DemandSignalResponse(**asdict(signal)) for signal in signals]

    @router.get(
        "/inventory/positions",
        response_model=InventoryPositionResponse,
        tags=["inventory"],
    )
    def get_inventory_position(
        store_id: str = Query(min_length=1), product_id: str = Query(min_length=1)
    ) -> InventoryPositionResponse:
        try:
            position = inventory_risk_service.get_position(store_id, product_id)
        except PlanningDataNotFoundError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(error),
            ) from error
        return InventoryPositionResponse(**asdict(position))

    @router.get(
        "/inventory/risks",
        response_model=InventoryRiskResponse,
        tags=["inventory"],
    )
    def get_inventory_risk(
        store_id: str = Query(min_length=1), product_id: str = Query(min_length=1)
    ) -> InventoryRiskResponse:
        try:
            risk = inventory_risk_service.get_risk(store_id, product_id)
        except PlanningDataNotFoundError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(error),
            ) from error
        except InsufficientHistoryError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(error),
            ) from error
        except (ForecastingFailedError, InventoryRiskUnavailableError) as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(error),
            ) from error
        return InventoryRiskResponse(**asdict(risk))

    @router.get(
        "/exceptions",
        response_model=list[PlanningExceptionResponse],
        tags=["exceptions"],
    )
    def get_planning_exceptions(
        store_id: str = Query(min_length=1),
        product_id: str = Query(min_length=1),
        exception_type: Annotated[ExceptionType | None, Query()] = None,
        severity: Annotated[ExceptionSeverity | None, Query()] = None,
        exception_status: Annotated[ExceptionStatus | None, Query(alias="status")] = None,
    ) -> list[PlanningExceptionResponse]:
        try:
            exceptions = planning_exception_service.get_exceptions(
                store_id,
                product_id,
                exception_type=exception_type,
                severity=severity,
                status=exception_status,
            )
        except PlanningDataNotFoundError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(error),
            ) from error
        except (ForecastPreviewLimitError, InsufficientHistoryError) as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(error),
            ) from error
        except (ForecastingFailedError, InventoryRiskUnavailableError) as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(error),
            ) from error
        return [PlanningExceptionResponse(**asdict(exception)) for exception in exceptions]

    @router.post(
        "/forecast-previews",
        response_model=ForecastPreviewResponse,
        status_code=status.HTTP_200_OK,
        tags=["forecasting"],
    )
    def create_forecast_preview(request: ForecastPreviewRequest) -> ForecastPreviewResponse:
        try:
            preview = preview_service.create(
                request.store_id,
                request.product_id,
                horizon_months=request.horizon_months,
                interval_level=request.interval_level,
            )
        except PlanningDataNotFoundError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        except (ForecastPreviewLimitError, InsufficientHistoryError) as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
            ) from error
        except ForecastingFailedError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
            ) from error

        result = preview.result
        return ForecastPreviewResponse(
            forecast_id=result.forecast_id,
            store_id=preview.store_id,
            product=ProductResponse(**asdict(preview.product)),
            selected_model=result.selected_model,
            training_cutoff=result.training_cutoff,
            horizon_months=result.horizon_months,
            interval_level=result.interval_level,
            intermittent_demand=result.intermittent_demand,
            validation_origins=result.validation_origins,
            selected_metrics=ForecastMetricsResponse(**asdict(result.selected_metrics)),
            evaluations=[
                ModelEvaluationResponse(
                    model_name=evaluation.model_name,
                    status=evaluation.status,
                    validation_origins=evaluation.validation_origins,
                    metrics=(
                        ForecastMetricsResponse(**asdict(evaluation.metrics))
                        if evaluation.metrics is not None
                        else None
                    ),
                    failure_detail=evaluation.failure_detail,
                )
                for evaluation in result.evaluations
            ],
            forecasts=[ForecastPointResponse(**asdict(point)) for point in result.forecasts],
        )

    return router
