"""Configuration for reproducible offline forecast runs."""

from datetime import datetime
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ForecastRunConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    data_directory: Path
    output_root: Path
    data_version: str = Field(min_length=1)
    created_at: datetime
    horizon_months: int = Field(default=6, ge=1, le=12)
    interval_level: int = Field(default=90, ge=50, le=99)
    maximum_series: int | None = Field(default=None, ge=1)
    parquet_compression: Literal["snappy", "zstd"] = "zstd"

    @model_validator(mode="after")
    def validate_created_at(self) -> "ForecastRunConfig":
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must include a timezone")
        return self

    def resolved_data_directory(self, project_root: Path) -> Path:
        return (
            self.data_directory
            if self.data_directory.is_absolute()
            else project_root / self.data_directory
        )

    def resolved_output_root(self, project_root: Path) -> Path:
        return (
            self.output_root if self.output_root.is_absolute() else project_root / self.output_root
        )


def load_forecast_run_config(path: Path) -> ForecastRunConfig:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("forecast-run configuration must be a mapping")
    return ForecastRunConfig.model_validate(payload)
