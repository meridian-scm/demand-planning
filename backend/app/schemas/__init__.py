"""Pydantic request/response models for the public API."""

from app.schemas.analytics import (
    CategoryBreakdown,
    DashboardSummary,
    DemandTimeline,
    ExceptionBreakdown,
    ProductDetail,
    TrendEntry,
    TrendsResponse,
)
from app.schemas.common import HealthResponse, Page, StatusResponse
from app.schemas.exception import ExceptionRead, ExceptionStatusUpdate
from app.schemas.forecast import (
    ForecastPointRead,
    ForecastPreview,
    ForecastRead,
    ForecastRunCreate,
    ForecastRunRead,
)
from app.schemas.ingestion import IngestionReport
from app.schemas.insight import InsightRead, InsightRequest
from app.schemas.inventory import InventoryRead, InventoryUpsert
from app.schemas.location import LocationCreate, LocationRead
from app.schemas.product import ProductCreate, ProductRead, ProductUpdate
from app.schemas.sales import SalesBulkCreate, SalesCreate, SalesRead

__all__ = [
    "CategoryBreakdown",
    "DashboardSummary",
    "DemandTimeline",
    "ExceptionBreakdown",
    "ExceptionRead",
    "ExceptionStatusUpdate",
    "ForecastPointRead",
    "ForecastPreview",
    "ForecastRead",
    "ForecastRunCreate",
    "ForecastRunRead",
    "HealthResponse",
    "IngestionReport",
    "InsightRead",
    "InsightRequest",
    "InventoryRead",
    "InventoryUpsert",
    "LocationCreate",
    "LocationRead",
    "Page",
    "ProductCreate",
    "ProductDetail",
    "ProductRead",
    "ProductUpdate",
    "SalesBulkCreate",
    "SalesCreate",
    "SalesRead",
    "StatusResponse",
    "TrendEntry",
    "TrendsResponse",
]
