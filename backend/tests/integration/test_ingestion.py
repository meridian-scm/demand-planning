"""Integration tests for CSV ingestion against a real (SQLite) database."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ValidationError
from app.models import Location, Product, SalesHistory
from app.services.ingestion import SalesIngestionService

pytestmark = pytest.mark.integration


def _add_product(db: Session, sku: str = "SKU-1") -> Product:
    product = Product(sku=sku, name="Widget", category="Test")
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


class TestHappyPath:
    def test_imports_well_formed_csv(self, db_session: Session) -> None:
        _add_product(db_session, "SKU-1")
        csv_content = "sku,period_start,units_sold\nSKU-1,2025-01-01,100\nSKU-1,2025-02-01,120\n"

        result = SalesIngestionService(db_session).ingest_csv(csv_content)

        assert result.rows_imported == 2
        assert result.rows_rejected == 0
        rows = db_session.execute(select(SalesHistory)).scalars().all()
        assert len(rows) == 2

    def test_accepts_alternate_column_names(self, db_session: Session) -> None:
        _add_product(db_session, "SKU-1")
        csv_content = "Item Code,Month,Quantity\nSKU-1,Jan-2025,50\n"

        result = SalesIngestionService(db_session).ingest_csv(csv_content)

        assert result.rows_imported == 1

    def test_reupload_updates_rather_than_duplicates(self, db_session: Session) -> None:
        _add_product(db_session, "SKU-1")
        service = SalesIngestionService(db_session)
        service.ingest_csv("sku,period_start,units_sold\nSKU-1,2025-01-01,100\n")
        result = service.ingest_csv("sku,period_start,units_sold\nSKU-1,2025-01-01,150\n")

        assert result.rows_updated == 1
        assert result.rows_imported == 0
        rows = db_session.execute(select(SalesHistory)).scalars().all()
        assert len(rows) == 1
        assert rows[0].units_sold == 150

    def test_location_column_resolves_to_location_id(self, db_session: Session) -> None:
        _add_product(db_session, "SKU-1")
        location = Location(code="DC-EAST", name="East DC", region="East")
        db_session.add(location)
        db_session.commit()

        csv_content = "sku,period_start,units_sold,location_code\nSKU-1,2025-01-01,10,DC-EAST\n"
        result = SalesIngestionService(db_session).ingest_csv(csv_content)

        assert result.rows_imported == 1
        row = db_session.execute(select(SalesHistory)).scalar_one()
        assert row.location_id == location.id


class TestRowLevelErrors:
    def test_unknown_sku_is_rejected_not_fatal(self, db_session: Session) -> None:
        _add_product(db_session, "SKU-1")
        csv_content = (
            "sku,period_start,units_sold\n"
            "SKU-1,2025-01-01,100\n"
            "SKU-UNKNOWN,2025-01-01,50\n"
        )
        result = SalesIngestionService(db_session).ingest_csv(csv_content)

        assert result.rows_imported == 1
        assert result.rows_rejected == 1
        assert "SKU-UNKNOWN" in result.unknown_skus

    def test_negative_units_rejected(self, db_session: Session) -> None:
        _add_product(db_session, "SKU-1")
        csv_content = "sku,period_start,units_sold\nSKU-1,2025-01-01,-5\n"
        result = SalesIngestionService(db_session).ingest_csv(csv_content)

        assert result.rows_rejected == 1
        assert result.rows_imported == 0

    def test_non_numeric_units_rejected(self, db_session: Session) -> None:
        _add_product(db_session, "SKU-1")
        csv_content = "sku,period_start,units_sold\nSKU-1,2025-01-01,abc\n"
        result = SalesIngestionService(db_session).ingest_csv(csv_content)

        assert result.rows_rejected == 1

    def test_unparseable_date_rejected(self, db_session: Session) -> None:
        _add_product(db_session, "SKU-1")
        csv_content = "sku,period_start,units_sold\nSKU-1,not-a-date,10\n"
        result = SalesIngestionService(db_session).ingest_csv(csv_content)

        assert result.rows_rejected == 1

    def test_mixed_valid_and_invalid_rows_commits_only_valid_ones(self, db_session: Session) -> None:
        _add_product(db_session, "SKU-1")
        csv_content = (
            "sku,period_start,units_sold\n"
            "SKU-1,2025-01-01,100\n"
            "SKU-1,2025-02-01,-1\n"
            "SKU-1,2025-03-01,200\n"
        )
        result = SalesIngestionService(db_session).ingest_csv(csv_content)

        assert result.rows_imported == 2
        assert result.rows_rejected == 1


class TestFileLevelValidation:
    def test_missing_required_column_raises(self, db_session: Session) -> None:
        csv_content = "sku,units_sold\nSKU-1,100\n"
        with pytest.raises(ValidationError):
            SalesIngestionService(db_session).ingest_csv(csv_content)

    def test_empty_file_raises(self, db_session: Session) -> None:
        csv_content = "sku,period_start,units_sold\n"
        with pytest.raises(ValidationError):
            SalesIngestionService(db_session).ingest_csv(csv_content)

    def test_garbage_content_raises_validation_error(self, db_session: Session) -> None:
        with pytest.raises(ValidationError):
            SalesIngestionService(db_session).ingest_csv(b"\x00\x01\x02not-csv-at-all")


class TestPeriodNormalisation:
    def test_mid_month_date_normalised_to_first(self, db_session: Session) -> None:
        _add_product(db_session, "SKU-1")
        csv_content = "sku,period_start,units_sold\nSKU-1,2025-01-17,75\n"
        SalesIngestionService(db_session).ingest_csv(csv_content)

        row = db_session.execute(select(SalesHistory)).scalar_one()
        assert row.period_start == date(2025, 1, 1)
