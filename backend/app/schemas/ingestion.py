"""CSV ingestion report schema."""

from __future__ import annotations

from pydantic import BaseModel


class IngestionReport(BaseModel):
    """Row-level outcome of a sales-history upload."""

    rows_received: int
    rows_imported: int
    rows_updated: int
    rows_rejected: int
    errors: list[dict]
    error_count: int
    unknown_skus: list[str]
