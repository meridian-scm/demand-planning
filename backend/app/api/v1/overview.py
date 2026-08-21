"""Planner-facing portfolio Overview endpoint."""

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.application.overview import OverviewService, OverviewUnavailableError
from app.schemas.overview import PortfolioOverviewResponse


def create_overview_router(service: OverviewService) -> APIRouter:
    router = APIRouter()

    @router.get(
        "/dashboard/summary",
        response_model=PortfolioOverviewResponse,
        tags=["dashboard"],
    )
    def get_dashboard_summary(
        run_id: Annotated[str | None, Query(min_length=1)] = None,
        store_id: Annotated[str | None, Query(min_length=1)] = None,
        exception_limit: Annotated[int, Query(ge=1, le=50)] = 10,
    ) -> PortfolioOverviewResponse:
        try:
            overview = service.get_overview(
                run_id=run_id,
                store_id=store_id,
                exception_limit=exception_limit,
            )
        except OverviewUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(error),
            ) from error
        return PortfolioOverviewResponse.model_validate(asdict(overview))

    return router
