"""Read-only endpoints for immutable forecast-run artifacts."""

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.ports.repositories.forecast_runs import ForecastRunReadRepository
from app.schemas.forecast_runs import (
    ForecastRunResponse,
    ForecastSeriesResultResponse,
    StoredForecastResponse,
    StoredModelEvaluationResponse,
)


def create_forecast_run_router(repository: ForecastRunReadRepository) -> APIRouter:
    router = APIRouter()

    @router.get("/forecast-runs", response_model=list[ForecastRunResponse], tags=["forecast-runs"])
    def list_forecast_runs() -> list[ForecastRunResponse]:
        return [ForecastRunResponse(**asdict(run)) for run in repository.list_runs()]

    @router.get(
        "/forecast-runs/{run_id}", response_model=ForecastRunResponse, tags=["forecast-runs"]
    )
    def get_forecast_run(run_id: str) -> ForecastRunResponse:
        run = repository.get_run(run_id)
        if run is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Forecast run {run_id!r} does not exist.",
            )
        return ForecastRunResponse(**asdict(run))

    @router.get(
        "/forecast-runs/{run_id}/series",
        response_model=list[ForecastSeriesResultResponse],
        tags=["forecast-runs"],
    )
    def list_forecast_series(
        run_id: str,
        store_id: Annotated[str | None, Query(min_length=1)] = None,
        query: Annotated[str, Query(max_length=100)] = "",
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
    ) -> list[ForecastSeriesResultResponse]:
        _require_run(repository, run_id)
        results = repository.list_series(
            run_id, store_id=store_id, query=query.strip(), limit=limit
        )
        return [ForecastSeriesResultResponse(**asdict(result)) for result in results]

    @router.get(
        "/forecast-runs/{run_id}/evaluations",
        response_model=list[StoredModelEvaluationResponse],
        tags=["forecast-runs"],
    )
    def get_model_evaluations(
        run_id: str,
        store_id: str = Query(min_length=1),
        product_id: str = Query(min_length=1),
    ) -> list[StoredModelEvaluationResponse]:
        _require_run(repository, run_id)
        evaluations = repository.get_evaluations(run_id, store_id, product_id)
        return [StoredModelEvaluationResponse(**asdict(item)) for item in evaluations]

    @router.get(
        "/forecasts",
        response_model=list[StoredForecastResponse],
        tags=["forecast-runs"],
    )
    def get_stored_forecasts(
        run_id: str = Query(min_length=1),
        store_id: str = Query(min_length=1),
        product_id: str = Query(min_length=1),
    ) -> list[StoredForecastResponse]:
        _require_run(repository, run_id)
        forecasts = repository.get_forecasts(run_id, store_id, product_id)
        return [StoredForecastResponse(**asdict(item)) for item in forecasts]

    return router


def _require_run(repository: ForecastRunReadRepository, run_id: str) -> None:
    if repository.get_run(run_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Forecast run {run_id!r} does not exist.",
        )
