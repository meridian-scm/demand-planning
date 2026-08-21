"""Load versioned artifact schemas and convert records to Arrow tables."""

from pathlib import Path

import pandas as pd
import pyarrow as pa
from pydantic import BaseModel, ConfigDict

from app.data_generation.models import ARTIFACT_NAMES, ArtifactName


class ColumnDefinition(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    type: str
    nullable: bool


class SchemaDocument(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str
    artifacts: dict[str, list[ColumnDefinition]]


def _arrow_type(type_name: str) -> pa.DataType:
    type_mapping: dict[str, pa.DataType] = {
        "string": pa.string(),
        "bool": pa.bool_(),
        "int32": pa.int32(),
        "int64": pa.int64(),
        "float64": pa.float64(),
        "date32": pa.date32(),
        "timestamp_utc": pa.timestamp("us", tz="UTC"),
        "decimal_10_2": pa.decimal128(10, 2),
    }
    try:
        return type_mapping[type_name]
    except KeyError as error:
        raise ValueError(f"Unsupported artifact column type: {type_name}") from error


def load_artifact_schemas(path: Path, expected_version: str) -> dict[ArtifactName, pa.Schema]:
    """Load the external schema contract and compile it to Arrow schemas."""

    document = SchemaDocument.model_validate_json(path.read_text(encoding="utf-8"))
    if document.schema_version != expected_version:
        raise ValueError(
            f"Schema version mismatch: config={expected_version}, file={document.schema_version}"
        )
    if set(document.artifacts) != set(ARTIFACT_NAMES):
        raise ValueError("Schema document must define exactly the expected artifacts")

    return {
        name: pa.schema(
            [
                pa.field(column.name, _arrow_type(column.type), nullable=column.nullable)
                for column in document.artifacts[name]
            ],
            metadata={b"meridian_schema_version": expected_version.encode()},
        )
        for name in ARTIFACT_NAMES
    }


def dataframe_to_arrow(dataframe: pd.DataFrame, schema: pa.Schema) -> pa.Table:
    """Convert a frame using the declared contract rather than inferred Parquet types."""

    return pa.Table.from_pandas(dataframe, schema=schema, preserve_index=False, safe=True)
