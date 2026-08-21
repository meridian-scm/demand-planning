"""Fail-fast schema and completeness validation tests."""

from pathlib import Path

import pytest
from app.data_generation.config import GeneratorConfig
from app.data_generation.generator import generate_artifacts
from app.data_generation.models import ArtifactBundle
from app.data_generation.schemas import load_artifact_schemas
from app.data_generation.validation import ArtifactValidationError, validate_artifacts


def test_validation_accepts_complete_test_profile(
    generator_config: GeneratorConfig, project_root: Path
) -> None:
    bundle = generate_artifacts(generator_config)
    schemas = load_artifact_schemas(
        generator_config.resolved_schema_path(project_root), generator_config.schema_version
    )

    summary = validate_artifacts(bundle, generator_config, schemas)

    assert summary.row_counts["demand_history.parquet"] == 7200
    assert summary.period_start == "2021-01-01"
    assert summary.period_end == "2025-12-01"


def test_missing_month_is_rejected_instead_of_becoming_zero(
    generator_config: GeneratorConfig, project_root: Path
) -> None:
    bundle = generate_artifacts(generator_config)
    incomplete_tables = dict(bundle.tables)
    incomplete_tables["demand_history.parquet"] = (
        bundle.table("demand_history.parquet").iloc[:-1].copy()
    )
    incomplete = ArtifactBundle(tables=incomplete_tables)
    schemas = load_artifact_schemas(
        generator_config.resolved_schema_path(project_root), generator_config.schema_version
    )

    with pytest.raises(ArtifactValidationError, match="demand row count is incorrect"):
        validate_artifacts(incomplete, generator_config, schemas)


def test_duplicate_sku_is_rejected(generator_config: GeneratorConfig, project_root: Path) -> None:
    bundle = generate_artifacts(generator_config)
    invalid_tables = dict(bundle.tables)
    products = bundle.table("products.parquet").copy()
    products.loc[1, "sku"] = products.loc[0, "sku"]
    invalid_tables["products.parquet"] = products
    schemas = load_artifact_schemas(
        generator_config.resolved_schema_path(project_root), generator_config.schema_version
    )

    with pytest.raises(ArtifactValidationError, match="SKU must be globally unique"):
        validate_artifacts(ArtifactBundle(tables=invalid_tables), generator_config, schemas)
