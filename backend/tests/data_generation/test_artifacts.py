"""Parquet publication, manifest, checksum, and CLI tests."""

import json
from pathlib import Path

import pytest
from app.data_generation.artifacts import (
    ArtifactPublicationError,
    load_published_bundle,
    publish_artifacts,
    validate_published_artifacts,
)
from app.data_generation.cli import main
from app.data_generation.config import GeneratorConfig
from app.data_generation.generator import generate_artifacts
from app.data_generation.models import ARTIFACT_NAMES


def _temporary_config(generator_config: GeneratorConfig, output: Path) -> GeneratorConfig:
    return generator_config.model_copy(update={"output_directory": output})


def test_publication_writes_versioned_parquet_and_verified_manifest(
    generator_config: GeneratorConfig, project_root: Path, tmp_path: Path
) -> None:
    config = _temporary_config(generator_config, tmp_path / "published")
    manifest = publish_artifacts(generate_artifacts(config), config, project_root)

    assert (tmp_path / "published/manifest.json").is_file()
    assert set(manifest.artifacts) == set(ARTIFACT_NAMES)
    assert manifest.row_counts["demand_history.parquet"] == 7200
    assert manifest.generation_run_id.startswith("generation-")
    assert manifest.parquet_compression == "zstd"
    for artifact_name in ARTIFACT_NAMES:
        assert (tmp_path / "published" / artifact_name).is_file()
        assert manifest.artifacts[artifact_name].sha256

    summary = validate_published_artifacts(config, project_root)
    assert summary.row_counts == manifest.row_counts
    loaded, loaded_manifest = load_published_bundle(config, project_root)
    assert len(loaded.table("stores.parquet")) == 5
    assert loaded_manifest == manifest


def test_publication_refuses_to_replace_existing_version(
    generator_config: GeneratorConfig, project_root: Path, tmp_path: Path
) -> None:
    config = _temporary_config(generator_config, tmp_path / "published")
    bundle = generate_artifacts(config)
    publish_artifacts(bundle, config, project_root)

    with pytest.raises(ArtifactPublicationError, match="Output already exists"):
        publish_artifacts(bundle, config, project_root)


def test_checksum_drift_is_rejected(
    generator_config: GeneratorConfig, project_root: Path, tmp_path: Path
) -> None:
    config = _temporary_config(generator_config, tmp_path / "published")
    publish_artifacts(generate_artifacts(config), config, project_root)
    artifact_path = tmp_path / "published/stores.parquet"
    artifact_path.write_bytes(artifact_path.read_bytes() + b"corruption")

    with pytest.raises(ArtifactPublicationError, match="checksum mismatch"):
        load_published_bundle(config, project_root)


def test_cli_generates_and_validates_an_overridden_output(
    project_root: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "cli-output"
    config_path = project_root / "config/data/test.yaml"

    assert main(["--config", str(config_path), "--output", str(output)]) == 0
    generated = json.loads(capsys.readouterr().out)
    assert generated["status"] == "generated"
    assert generated["row_counts"]["demand_history.parquet"] == 7200

    assert (
        main(
            [
                "--config",
                str(config_path),
                "--output",
                str(output),
                "--validate-only",
            ]
        )
        == 0
    )
    validated = json.loads(capsys.readouterr().out)
    assert validated["status"] == "valid"
