"""AI-insight endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ValidationError
from app.db.session import get_db
from app.models import Insight
from app.models.enums import InsightScope
from app.schemas import InsightRead, InsightRequest
from app.services.planning import PlanningService

router = APIRouter(prefix="/insights", tags=["insights"])


@router.post("", response_model=InsightRead, status_code=201)
def generate_insight(payload: InsightRequest, db: Session = Depends(get_db)) -> Insight:
    service = PlanningService(db)

    if payload.scope == InsightScope.PRODUCT:
        if payload.product_id is None:
            raise ValidationError("product_id is required when scope is 'product'.")
        return service.generate_product_insight(payload.product_id, persist=payload.persist)

    return service.generate_portfolio_insight(persist=payload.persist)


@router.get("", response_model=list[InsightRead])
def list_insights(
    db: Session = Depends(get_db), product_id: int | None = None, limit: int = 20
) -> list[Insight]:
    statement = select(Insight).order_by(Insight.created_at.desc()).limit(limit)
    if product_id is not None:
        statement = statement.where(Insight.product_id == product_id)
    return list(db.execute(statement).scalars())
