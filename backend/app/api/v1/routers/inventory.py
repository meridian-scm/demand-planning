"""Inventory-snapshot endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import InventorySnapshot
from app.schemas import InventoryRead, InventoryUpsert

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("", response_model=list[InventoryRead])
def list_inventory(
    db: Session = Depends(get_db), product_id: int | None = Query(default=None)
) -> list[InventorySnapshot]:
    statement = select(InventorySnapshot)
    if product_id is not None:
        statement = statement.where(InventorySnapshot.product_id == product_id)
    statement = statement.order_by(InventorySnapshot.snapshot_date.desc())
    return list(db.execute(statement).scalars())


@router.post("", response_model=InventoryRead, status_code=201)
def upsert_inventory(payload: InventoryUpsert, db: Session = Depends(get_db)) -> InventorySnapshot:
    existing = db.execute(
        select(InventorySnapshot).where(
            InventorySnapshot.product_id == payload.product_id,
            InventorySnapshot.location_id == payload.location_id,
            InventorySnapshot.snapshot_date == payload.snapshot_date,
        )
    ).scalar_one_or_none()

    if existing is None:
        existing = InventorySnapshot(**payload.model_dump())
        db.add(existing)
    else:
        for field, value in payload.model_dump().items():
            setattr(existing, field, value)

    db.commit()
    db.refresh(existing)
    return existing
