"""Atomic Parquet publication and checksum-backed validation."""

import json
import platform
import shutil
import tempfile
from hashlib import sha256
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pydantic

from app.data_generation.config import GeneratorConfig
from app.data_generation.generator import GENERATOR_VERSION
from app.data_generation.models import (
    ARTIFACT_NAMES,
    ArtifactBundle,
    ArtifactManifest,
    ArtifactMetadata,
    ArtifactName,
)
from app.data_generation.schemas import dataframe_to_arrow, load_artifact_schemas
from app.data_generation.validation import ValidationSummary, validate_artifacts


class ArtifactPublicationError(RuntimeError):
    """Raised when an artifact set cannot be safely published or verified."""


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as artifact_file:
        for chunk in iter(lambda: artifact_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _configuration_sha256(config: GeneratorConfig) -> str:
    logical_config = config.model_dump(mode="json")
    logical_config.pop("output_directory")
    logical_config.pop("schema_path")
    canonical = json.dumps(logical_config, sort_keys=True, separators=(",", ":")).encode()
    return sha256(canonical).hexdigest()


def _build_manifest(
    config: GeneratorConfig,
    summary: ValidationSummary,
    output_directory: Path,
) -> ArtifactManifest:
    metadata = {
        name: ArtifactMetadata(
            sha256=_file_sha256(output_directory / name),
            size_bytes=(output_directory / name).stat().st_size,
            row_count=summary.row_counts[name],
        )
        for name in ARTIFACT_NAMES
    }
    configuration_sha256 = _configuration_sha256(config)
    return ArtifactManifest(
        schema_version=config.schema_version,
        data_version=config.data_version,
        generator_version=GENERATOR_VERSION,
        generation_run_id=f"generation-{configuration_sha256[:16]}",
        profile=config.profile,
        parquet_compression=config.parquet_compression,
        configuration_sha256=configuration_sha256,
        random_seed=config.random_seed,
        generated_at=config.generation_timestamp_utc,
        period_start=summary.period_start,
        period_end=summary.period_end,
        row_counts=summary.row_counts,
        artifacts=metadata,
        tool_versions={
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "pyarrow": pa.__version__,
            "pydantic": pydantic.__version__,
        },
    )


def publish_artifacts(
    bundle: ArtifactBundle,
    config: GeneratorConfig,
    project_root: Path,
    *,
    overwrite: bool = False,
) -> ArtifactManifest:
    """Validate and atomically publish a complete versioned artifact directory."""

    output_directory = config.resolved_output_directory(project_root)
    schemas = load_artifact_schemas(
        config.resolved_schema_path(project_root), config.schema_version
    )
    summary = validate_artifacts(bundle, config, schemas)
    output_directory.parent.mkdir(parents=True, exist_ok=True)
    if output_directory.exists() and not overwrite:
        raise ArtifactPublicationError(
            f"Output already exists: {output_directory}. Use a new data version or --overwrite."
        )

    temporary_directory = Path(
        tempfile.mkdtemp(prefix=f".{output_directory.name}-", dir=output_directory.parent)
    )
    try:
        for name in ARTIFACT_NAMES:
            table = dataframe_to_arrow(bundle.table(name), schemas[name])
            pq.write_table(
                table,
                temporary_directory / name,
                compression=config.parquet_compression,
                write_statistics=True,
            )
        manifest = _build_manifest(config, summary, temporary_directory)
        (temporary_directory / "manifest.json").write_text(
            manifest.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        if output_directory.exists():
            shutil.rmtree(output_directory)
        temporary_directory.rename(output_directory)
    except Exception:
        shutil.rmtree(temporary_directory, ignore_errors=True)
        raise
    return manifest


def load_published_bundle(
    config: GeneratorConfig, project_root: Path
) -> tuple[ArtifactBundle, ArtifactManifest]:
    """Load a complete artifact set and reject missing files or checksum drift."""

    output_directory = config.resolved_output_directory(project_root)
    manifest_path = output_directory / "manifest.json"
    if not manifest_path.is_file():
        raise ArtifactPublicationError(f"Manifest not found: {manifest_path}")
    manifest = ArtifactManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    if manifest.configuration_sha256 != _configuration_sha256(config):
        raise ArtifactPublicationError("Manifest configuration checksum does not match the profile")

    tables: dict[ArtifactName, pd.DataFrame] = {}
    for name in ARTIFACT_NAMES:
        path = output_directory / name
        if not path.is_file():
            raise ArtifactPublicationError(f"Artifact not found: {path}")
        metadata = manifest.artifacts.get(name)
        if metadata is None or _file_sha256(path) != metadata.sha256:
            raise ArtifactPublicationError(f"Artifact checksum mismatch: {name}")
        tables[name] = pq.read_table(path).to_pandas()
    return ArtifactBundle(tables=tables), manifest


def validate_published_artifacts(config: GeneratorConfig, project_root: Path) -> ValidationSummary:
    """Re-read published files and apply checksum, schema, and logical validation."""

    bundle, manifest = load_published_bundle(config, project_root)
    schemas = load_artifact_schemas(
        config.resolved_schema_path(project_root), config.schema_version
    )
    summary = validate_artifacts(bundle, config, schemas)
    if summary.row_counts != manifest.row_counts:
        raise ArtifactPublicationError("Manifest row counts do not match validated artifacts")
    return summary
