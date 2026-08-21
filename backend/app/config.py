"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated runtime settings with safe local-development defaults."""

    model_config = SettingsConfigDict(
        env_prefix="MERIDIAN_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"
    artifact_directory: Path = Path("../data/generated")
    artifact_data_version: str = "test-v1"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    preview_max_horizon_months: int = Field(default=12, ge=1, le=12)
    preview_max_series: int = Field(default=1, ge=1, le=1)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    @property
    def artifact_version_directory(self) -> Path:
        """Resolve the selected immutable artifact version below the artifact root."""

        return self.artifact_directory / self.artifact_data_version

    @property
    def forecast_run_directory(self) -> Path:
        """Locate immutable derived runs for the selected base data version."""

        return self.artifact_version_directory / "forecast_runs"


@lru_cache
def get_settings() -> Settings:
    """Return one validated settings object per process."""

    return Settings()
