"""Forecasting endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.db.session import get_db
from app.models import Forecast, ForecastRun
from app.models.enums import ForecastModel
from app.schemas import ForecastPreview, ForecastRead, ForecastRunCreate, ForecastRunRead
from app.schemas.forecast import ForecastPointRead
from app.services.planning import PlanningService, get_product_or_404

router = APIRouter(prefix="/forecasts", tags=["forecasts"])


@router.post("/runs", response_model=ForecastRunRead, status_code=201)
def create_forecast_run(payload: ForecastRunCreate, db: Session = Depends(get_db)) -> ForecastRun:
    """Run a full forecasting cycle and refresh planning exceptions."""
    service = PlanningService(db)
    return service.run_forecast(
        horizon=payload.horizon,
        model=payload.model.value,
        product_ids=payload.product_ids,
        run_label=payload.run_label,
        detect_exceptions=payload.detect_exceptions,
    )


@router.get("/runs", response_model=list[ForecastRunRead])
def list_forecast_runs(
    db: Session = Depends(get_db), limit: int = Query(default=20, ge=1, le=200)
) -> list[ForecastRun]:
    return list(
        db.execute(select(ForecastRun).order_by(ForecastRun.started_at.desc()).limit(limit)).scalars()
    )


@router.get("/runs/{run_id}", response_model=ForecastRunRead)
def get_forecast_run(run_id: int, db: Session = Depends(get_db)) -> ForecastRun:
    run = db.get(ForecastRun, run_id)
    if run is None:
        raise NotFoundError(f"Forecast run {run_id} not found.", details={"run_id": run_id})
    return run


@router.get("/runs/{run_id}/lines", response_model=list[ForecastRead])
def list_forecast_lines(
    run_id: int, db: Session = Depends(get_db), product_id: int | None = Query(default=None)
) -> list[Forecast]:
    run = db.get(ForecastRun, run_id)
    if run is None:
        raise NotFoundError(f"Forecast run {run_id} not found.", details={"run_id": run_id})

    statement = select(Forecast).where(Forecast.run_id == run_id)
    if product_id is not None:
        statement = statement.where(Forecast.product_id == product_id)
    return list(db.execute(statement.order_by(Forecast.product_id, Forecast.period_start)).scalars())


@router.get("/preview/{product_id}", response_model=ForecastPreview)
def preview_forecast(
    product_id: int,
    db: Session = Depends(get_db),
    horizon: int = Query(default=6, ge=1, le=36),
    model: ForecastModel = Query(default=ForecastModel.AUTO),
) -> ForecastPreview:
    """Forecast one product without persisting anything — used by the what-if UI."""
    product = get_product_or_404(db, product_id)
    service = PlanningService(db)
    _, result = service.forecast_product(
        product_id, horizon=horizon, model=model.value, persist=False
    )

    return ForecastPreview(
        product_id=product.id,
        sku=product.sku,
        name=product.name,
        model_used=result.model_used,
        history_periods=result.history_periods,
        confidence_level=result.confidence_level,
        mape=result.metrics.mape,
        wape=result.metrics.wape,
        rmse=result.metrics.rmse,
        candidates_evaluated=result.candidates_evaluated,
        points=[
            ForecastPointRead(
                period_start=point.period_start,
                forecast_units=point.forecast_units,
                lower_bound_units=point.lower_bound_units,
                upper_bound_units=point.upper_bound_units,
            )
            for point in result.points
        ],
        total_forecast_units=round(result.total_forecast_units, 2),
    )
