"""Shared backend test fixtures."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from app.config import Settings
from app.data_generation.artifacts import publish_artifacts
from app.data_generation.config import GeneratorConfig, load_generator_config
from app.data_generation.generator import generate_artifacts
from app.main import create_app
from fastapi.testclient import TestClient


@pytest.fixture
def artifact_directory(tmp_path: Path) -> Path:
    return tmp_path / "artifacts" / "test-v1"


@pytest.fixture
def client(artifact_directory: Path) -> Iterator[TestClient]:
    settings = Settings(
        environment="test",
        artifact_directory=artifact_directory.parent,
        artifact_data_version=artifact_directory.name,
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture
def generator_config(project_root: Path) -> GeneratorConfig:
    return load_generator_config(project_root / "config/data/test.yaml")


@pytest.fixture
def published_client(
    tmp_path: Path, generator_config: GeneratorConfig, project_root: Path
) -> Iterator[TestClient]:
    output_directory = tmp_path / "generated" / "test-v1"
    config = generator_config.model_copy(update={"output_directory": output_directory})
    publish_artifacts(generate_artifacts(config), config, project_root)
    settings = Settings(
        environment="test",
        artifact_directory=output_directory.parent,
        artifact_data_version=output_directory.name,
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client
