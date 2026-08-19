"""Dashboard and analytics endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas import (
    CategoryBreakdown,
    DashboardSummary,
    DemandTimeline,
    ExceptionBreakdown,
    ProductDetail,
    TrendsResponse,
)
from app.services.analytics import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary", response_model=DashboardSummary)
def get_summary(db: Session = Depends(get_db)) -> DashboardSummary:
    return DashboardSummary(**AnalyticsService(db).dashboard_summary())


@router.get("/timeline", response_model=DemandTimeline)
def get_timeline(
    db: Session = Depends(get_db), product_id: int | None = Query(default=None)
) -> DemandTimeline:
    return DemandTimeline(**AnalyticsService(db).demand_timeline(product_id=product_id))


@router.get("/trends", response_model=TrendsResponse)
def get_trends(db: Session = Depends(get_db), limit: int = Query(default=10, ge=1, le=50)) -> TrendsResponse:
    return TrendsResponse(**AnalyticsService(db).demand_trends(limit=limit))


@router.get("/categories", response_model=list[CategoryBreakdown])
def get_categories(db: Session = Depends(get_db)) -> list[CategoryBreakdown]:
    return [CategoryBreakdown(**row) for row in AnalyticsService(db).category_breakdown()]


@router.get("/exceptions/breakdown", response_model=list[ExceptionBreakdown])
def get_exception_breakdown(db: Session = Depends(get_db)) -> list[ExceptionBreakdown]:
    return [ExceptionBreakdown(**row) for row in AnalyticsService(db).exception_breakdown()]


@router.get("/products/{product_id}", response_model=ProductDetail)
def get_product_detail(product_id: int, db: Session = Depends(get_db)) -> ProductDetail:
    return ProductDetail(**AnalyticsService(db).product_detail(product_id))
