"""Aggregates every v1 router under a single ``APIRouter``."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routers import (
    analytics,
    exceptions,
    forecasts,
    insights,
    inventory,
    locations,
    products,
    sales,
)

api_router = APIRouter()
api_router.include_router(products.router)
api_router.include_router(locations.router)
api_router.include_router(sales.router)
api_router.include_router(inventory.router)
api_router.include_router(forecasts.router)
api_router.include_router(exceptions.router)
api_router.include_router(insights.router)
api_router.include_router(analytics.router)
