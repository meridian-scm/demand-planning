"""Location master-data endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError
from app.db.session import get_db
from app.models import Location
from app.schemas import LocationCreate, LocationRead

router = APIRouter(prefix="/locations", tags=["locations"])


@router.get("", response_model=list[LocationRead])
def list_locations(db: Session = Depends(get_db)) -> list[Location]:
    return list(db.execute(select(Location).order_by(Location.code)).scalars())


@router.post("", response_model=LocationRead, status_code=201)
def create_location(payload: LocationCreate, db: Session = Depends(get_db)) -> Location:
    location = Location(**payload.model_dump())
    db.add(location)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(
            f"A location with code {payload.code!r} already exists.", details={"code": payload.code}
        ) from exc
    db.refresh(location)
    return location
