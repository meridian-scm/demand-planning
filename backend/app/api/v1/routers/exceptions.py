"""Planning-exception endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import PlanningException, Product
from app.schemas import ExceptionRead, ExceptionStatusUpdate
from app.services.planning import PlanningService, severity_rank

router = APIRouter(prefix="/exceptions", tags=["exceptions"])


def _to_read(row: PlanningException, product: Product | None) -> ExceptionRead:
    read = ExceptionRead.model_validate(row)
    if product is not None:
        read.product_sku = product.sku
        read.product_name = product.name
    return read


@router.get("", response_model=list[ExceptionRead])
def list_exceptions(
    db: Session = Depends(get_db),
    status: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    exception_type: str | None = Query(default=None),
    product_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[ExceptionRead]:
    statement = select(PlanningException, Product).join(
        Product, Product.id == PlanningException.product_id
    )
    if status:
        statement = statement.where(PlanningException.status == status)
    if severity:
        statement = statement.where(PlanningException.severity == severity)
    if exception_type:
        statement = statement.where(PlanningException.exception_type == exception_type)
    if product_id is not None:
        statement = statement.where(PlanningException.product_id == product_id)

    rows = db.execute(statement.limit(limit)).all()
    results = [_to_read(exception, product) for exception, product in rows]
    results.sort(key=lambda item: (severity_rank(item.severity), item.detected_for_period), reverse=False)
    return results


@router.patch("/{exception_id}", response_model=ExceptionRead)
def update_exception_status(
    exception_id: int, payload: ExceptionStatusUpdate, db: Session = Depends(get_db)
) -> ExceptionRead:
    service = PlanningService(db)
    row = service.update_exception_status(exception_id, payload.status.value)
    product = db.get(Product, row.product_id)
    return _to_read(row, product)


@router.post("/products/{product_id}/refresh", response_model=list[ExceptionRead])
def refresh_product_exceptions(product_id: int, db: Session = Depends(get_db)) -> list[ExceptionRead]:
    """Re-run exception detection for one product on demand."""
    service = PlanningService(db)
    rows = service.detect_exceptions_for_product(product_id)
    product = db.get(Product, product_id)
    return [_to_read(row, product) for row in rows]
