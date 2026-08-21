"""Typed artifact and publication metadata."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

ArtifactName = Literal[
    "stores.parquet",
    "products.parquet",
    "store_products.parquet",
    "demand_history.parquet",
    "inventory_snapshots.parquet",
    "synthetic_ground_truth.parquet",
]

ARTIFACT_NAMES: tuple[ArtifactName, ...] = (
    "stores.parquet",
    "products.parquet",
    "store_products.parquet",
    "demand_history.parquet",
    "inventory_snapshots.parquet",
    "synthetic_ground_truth.parquet",
)


@dataclass(frozen=True, slots=True)
class ArtifactBundle:
    """In-memory logical records before Parquet publication."""

    tables: dict[ArtifactName, pd.DataFrame]

    def table(self, name: ArtifactName) -> pd.DataFrame:
        return self.tables[name]


class ArtifactMetadata(BaseModel):
    """Integrity metadata for one published artifact."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    size_bytes: int = Field(ge=0)
    row_count: int = Field(ge=0)


class ArtifactManifest(BaseModel):
    """Auditable identity and integrity metadata for an artifact set."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str
    data_version: str
    generator_version: str
    generation_run_id: str
    profile: Literal["test", "reference"]
    parquet_compression: Literal["snappy", "zstd"]
    configuration_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    random_seed: int
    generated_at: datetime
    period_start: date
    period_end: date
    row_counts: dict[str, int]
    artifacts: dict[str, ArtifactMetadata]
    tool_versions: dict[str, str]
