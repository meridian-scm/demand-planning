"""Shared backend test fixtures."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from app.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient


@pytest.fixture
def artifact_directory(tmp_path: Path) -> Path:
    return tmp_path / "artifacts"


@pytest.fixture
def client(artifact_directory: Path) -> Iterator[TestClient]:
    settings = Settings(environment="test", artifact_directory=artifact_directory)
    with TestClient(create_app(settings)) as test_client:
        yield test_client
