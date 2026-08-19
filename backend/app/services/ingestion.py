"""CSV ingestion for sales history.

Planners live in spreadsheets, so uploading a CSV is the primary way demand
data enters the system. The parser is deliberately forgiving about column
naming and date formats, and strict about the things that would silently
corrupt a forecast (non-numeric quantities, unknown SKUs, duplicate periods).
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import date

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ValidationError
from app.core.logging import get_logger
from app.models import Location, Product, SalesHistory

logger = get_logger(__name__)

#: Accepted spellings for each logical column, lower-cased and stripped.
COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "sku": ("sku", "product_sku", "item", "item_code", "material", "product_code"),
    "period_start": ("period_start", "period", "month", "date", "posting_date", "sales_month"),
    "units_sold": ("units_sold", "units", "quantity", "qty", "demand", "sales_units"),
    "revenue": ("revenue", "sales_value", "amount", "net_sales"),
    "location_code": ("location_code", "location", "site", "plant", "dc", "warehouse"),
    "channel": ("channel", "sales_channel"),
}

REQUIRED_COLUMNS = ("sku", "period_start", "units_sold")
MAX_ROWS = 250_000


@dataclass(slots=True)
class IngestionResult:
    """Outcome of one upload, reported back to the planner row by row."""

    rows_received: int = 0
    rows_imported: int = 0
    rows_updated: int = 0
    rows_rejected: int = 0
    errors: list[dict] = field(default_factory=list)
    unknown_skus: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "rows_received": self.rows_received,
            "rows_imported": self.rows_imported,
            "rows_updated": self.rows_updated,
            "rows_rejected": self.rows_rejected,
            # Cap the error list so a badly-formed 100k-row file does not
            # produce an unreadable response.
            "errors": self.errors[:50],
            "error_count": len(self.errors),
            "unknown_skus": sorted(set(self.unknown_skus))[:50],
        }


def _normalise_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Rename recognised column spellings onto the canonical names."""
    lookup: dict[str, str] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            lookup[alias] = canonical

    renamed = {}
    for column in frame.columns:
        key = str(column).strip().lower().replace(" ", "_")
        if key in lookup:
            renamed[column] = lookup[key]
    return frame.rename(columns=renamed)


def _to_period(value: object) -> date:
    """Parse a cell into the first day of its month."""
    parsed = pd.to_datetime(value, errors="coerce", dayfirst=False)
    if pd.isna(parsed):
        raise ValueError(f"unparseable period value {value!r}")
    return date(parsed.year, parsed.month, 1)


class SalesIngestionService:
    """Loads sales history from a CSV payload into the database."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def ingest_csv(self, content: bytes | str, *, source: str = "upload") -> IngestionResult:
        """Parse and persist a CSV of sales history.

        Existing (product, location, period) rows are updated rather than
        duplicated, so re-uploading a corrected extract is safe.
        """
        frame = self._read(content)
        result = IngestionResult(rows_received=len(frame))

        if result.rows_received == 0:
            raise ValidationError("The uploaded file contained no data rows.")
        if result.rows_received > MAX_ROWS:
            raise ValidationError(
                f"File has {result.rows_received:,} rows, above the {MAX_ROWS:,} row limit."
            )

        products = {
            product.sku.upper(): product
            for product in self.db.execute(select(Product)).scalars()
        }
        locations = {
            location.code.upper(): location
            for location in self.db.execute(select(Location)).scalars()
        }

        # Buffer the parsed rows, then write once — a partially-applied upload
        # is worse for a planner than a rejected one.
        staged: list[dict] = []

        for offset, row in enumerate(frame.to_dict("records"), start=2):  # +2 for the header line
            try:
                staged.append(self._parse_row(row, products, locations, source))
            except ValueError as exc:
                result.rows_rejected += 1
                result.errors.append({"line": offset, "error": str(exc)})
                sku = str(row.get("sku", "")).strip()
                if "unknown SKU" in str(exc) and sku:
                    result.unknown_skus.append(sku)

        for record in staged:
            existing = self.db.execute(
                select(SalesHistory).where(
                    SalesHistory.product_id == record["product_id"],
                    SalesHistory.location_id == record["location_id"],
                    SalesHistory.period_start == record["period_start"],
                )
            ).scalar_one_or_none()

            if existing is None:
                self.db.add(SalesHistory(**record))
                result.rows_imported += 1
            else:
                existing.units_sold = record["units_sold"]
                existing.revenue = record["revenue"]
                existing.channel = record["channel"]
                existing.source = record["source"]
                result.rows_updated += 1

        self.db.commit()
        logger.info(
            "ingested csv: %s imported, %s updated, %s rejected",
            result.rows_imported,
            result.rows_updated,
            result.rows_rejected,
        )
        return result

    def _read(self, content: bytes | str) -> pd.DataFrame:
        buffer = io.BytesIO(content) if isinstance(content, bytes) else io.StringIO(content)
        try:
            frame = pd.read_csv(buffer)
        except Exception as exc:  # noqa: BLE001 - surfaced to the planner as a 422
            raise ValidationError(f"Could not parse the file as CSV: {exc}") from exc

        frame = _normalise_columns(frame)
        missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
        if missing:
            raise ValidationError(
                f"Missing required column(s): {', '.join(missing)}.",
                details={
                    "missing": missing,
                    "found": [str(column) for column in frame.columns],
                    "accepted_aliases": {
                        key: list(value) for key, value in COLUMN_ALIASES.items()
                    },
                },
            )
        return frame

    def _parse_row(
        self,
        row: dict,
        products: dict[str, Product],
        locations: dict[str, Location],
        source: str,
    ) -> dict:
        sku = str(row.get("sku", "")).strip()
        if not sku or sku.lower() == "nan":
            raise ValueError("missing SKU")

        product = products.get(sku.upper())
        if product is None:
            raise ValueError(f"unknown SKU {sku!r} — create the product first")

        period_start = _to_period(row.get("period_start"))

        raw_units = row.get("units_sold")
        try:
            units = float(raw_units)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"non-numeric units_sold {raw_units!r}") from exc
        if pd.isna(units):
            raise ValueError("missing units_sold")
        if units < 0:
            raise ValueError(f"negative units_sold ({units})")

        location_id = None
        location_code = row.get("location_code")
        if location_code is not None and str(location_code).strip().lower() not in ("", "nan"):
            location = locations.get(str(location_code).strip().upper())
            if location is None:
                raise ValueError(f"unknown location {location_code!r}")
            location_id = location.id

        revenue = row.get("revenue")
        try:
            revenue_value = float(revenue) if revenue is not None and not pd.isna(revenue) else None
        except (TypeError, ValueError):
            revenue_value = None

        channel = row.get("channel")
        channel_value = (
            str(channel).strip()
            if channel is not None and str(channel).strip().lower() not in ("", "nan")
            else None
        )

        return {
            "product_id": product.id,
            "location_id": location_id,
            "period_start": period_start,
            "units_sold": int(round(units)),
            "revenue": revenue_value,
            "channel": channel_value,
            "source": source,
        }
