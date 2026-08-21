"""Versioned configuration for deterministic synthetic data."""

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DemandPattern = Literal[
    "stable",
    "growing",
    "declining",
    "seasonal",
    "strong_seasonal",
    "volatile",
    "intermittent",
    "spike",
    "drop",
    "new_product",
    "mature",
]

DEMAND_PATTERNS: tuple[DemandPattern, ...] = (
    "stable",
    "growing",
    "declining",
    "seasonal",
    "strong_seasonal",
    "volatile",
    "intermittent",
    "spike",
    "drop",
    "new_product",
    "mature",
)


class GeneratorConfig(BaseModel):
    """Complete reproducible input to one artifact generation run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    profile: Literal["test", "reference"]
    store_count: int = Field(ge=1, le=5)
    sku_count: int = Field(ge=1)
    month_count: int = Field(ge=12)
    end_period: date
    random_seed: int = Field(ge=0)
    generation_timestamp_utc: datetime
    output_directory: Path
    schema_path: Path
    schema_version: str = Field(min_length=1)
    data_version: str = Field(min_length=1)
    parquet_compression: Literal["snappy", "zstd"] = "zstd"
    pattern_weights: dict[DemandPattern, float]

    @field_validator("end_period")
    @classmethod
    def end_period_starts_a_month(cls, value: date) -> date:
        if value.day != 1:
            raise ValueError("end_period must be the first day of a month")
        return value

    @field_validator("generation_timestamp_utc")
    @classmethod
    def generation_timestamp_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
            raise ValueError("generation_timestamp_utc must be timezone-aware UTC")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def weights_are_complete_probabilities(self) -> Self:
        if set(self.pattern_weights) != set(DEMAND_PATTERNS):
            raise ValueError("pattern_weights must define every supported demand pattern")
        if any(weight <= 0 for weight in self.pattern_weights.values()):
            raise ValueError("pattern weights must be positive")
        if abs(sum(self.pattern_weights.values()) - 1.0) > 1e-9:
            raise ValueError("pattern weights must sum to 1.0")
        return self

    def resolved_output_directory(self, project_root: Path) -> Path:
        if self.output_directory.is_absolute():
            return self.output_directory
        return project_root / self.output_directory

    def resolved_schema_path(self, project_root: Path) -> Path:
        if self.schema_path.is_absolute():
            return self.schema_path
        return project_root / self.schema_path


def load_generator_config(path: Path) -> GeneratorConfig:
    """Load and validate a YAML generation profile."""

    with path.open(encoding="utf-8") as config_file:
        raw_config = yaml.safe_load(config_file)
    return GeneratorConfig.model_validate(raw_config)
