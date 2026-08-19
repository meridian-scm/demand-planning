"""Configuration contract tests."""

from pathlib import Path

import pytest
from app.config import Settings


def test_configuration_loads_from_prefixed_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MERIDIAN_ENVIRONMENT", "test")
    monkeypatch.setenv("MERIDIAN_ARTIFACT_DIRECTORY", "/tmp/meridian-test-artifacts")
    monkeypatch.setenv("MERIDIAN_PREVIEW_MAX_HORIZON_MONTHS", "6")

    settings = Settings()

    assert settings.environment == "test"
    assert settings.artifact_directory == Path("/tmp/meridian-test-artifacts")
    assert settings.preview_max_horizon_months == 6
    assert settings.preview_max_series == 1
