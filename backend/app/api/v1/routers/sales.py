"""Sales-history endpoints, including CSV upload."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ValidationError
from app.db.session import get_db
from app.models import SalesHistory
from app.schemas import IngestionReport, Page, SalesBulkCreate, SalesRead
from app.services.ingestion import SalesIngestionService

router = APIRouter(prefix="/sales", tags=["sales"])

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB


@router.get("", response_model=Page[SalesRead])
def list_sales(
    db: Session = Depends(get_db),
    product_id: int | None = Query(default=None),
    period_from: date | None = Query(default=None),
    period_to: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> Page[SalesRead]:
    statement = select(SalesHistory)
    if product_id is not None:
        statement = statement.where(SalesHistory.product_id == product_id)
    if period_from is not None:
        statement = statement.where(SalesHistory.period_start >= period_from)
    if period_to is not None:
        statement = statement.where(SalesHistory.period_start <= period_to)

    total = db.execute(select(func.count()).select_from(statement.subquery())).scalar_one()
    rows = db.execute(
        statement.order_by(SalesHistory.period_start.desc()).limit(limit).offset(offset)
    ).scalars().all()

    return Page(items=list(rows), total=total, limit=limit, offset=offset)


@router.post("/bulk", response_model=IngestionReport)
def bulk_upsert_sales(payload: SalesBulkCreate, db: Session = Depends(get_db)) -> IngestionReport:
    """Upsert sales rows submitted as JSON (used by the frontend's manual-entry form)."""
    imported = 0
    updated = 0
    for record in payload.records:
        existing = db.execute(
            select(SalesHistory).where(
                SalesHistory.product_id == record.product_id,
                SalesHistory.location_id == record.location_id,
                SalesHistory.period_start == record.period_start,
            )
        ).scalar_one_or_none()

        if existing is None:
            db.add(SalesHistory(**record.model_dump()))
            imported += 1
        else:
            existing.units_sold = record.units_sold
            existing.revenue = record.revenue
            existing.channel = record.channel
            existing.source = record.source
            updated += 1

    db.commit()
    return IngestionReport(
        rows_received=len(payload.records),
        rows_imported=imported,
        rows_updated=updated,
        rows_rejected=0,
        errors=[],
        error_count=0,
        unknown_skus=[],
    )


@router.post("/upload", response_model=IngestionReport)
async def upload_sales_csv(
    db: Session = Depends(get_db), file: UploadFile = File(...)
) -> IngestionReport:
    """Upload a CSV of historical demand. See ``SalesIngestionService`` for the format."""
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValidationError(
            f"File is too large ({len(content):,} bytes); the limit is "
            f"{MAX_UPLOAD_BYTES:,} bytes."
        )

    service = SalesIngestionService(db)
    result = service.ingest_csv(content, source=f"upload:{file.filename}")
    return IngestionReport(**result.as_dict())
