"""Fail-fast invariant validation for generated logical records."""

from collections.abc import Mapping
from dataclasses import dataclass

import pandas as pd
import pyarrow as pa

from app.data_generation.config import DEMAND_PATTERNS, GeneratorConfig
from app.data_generation.generator import INVENTORY_SCENARIOS
from app.data_generation.models import ARTIFACT_NAMES, ArtifactBundle, ArtifactName
from app.data_generation.schemas import dataframe_to_arrow


class ArtifactValidationError(ValueError):
    """Raised when generated data violates the approved contract."""


@dataclass(frozen=True, slots=True)
class ValidationSummary:
    """Counts and business period confirmed by validation."""

    row_counts: dict[str, int]
    period_start: str
    period_end: str


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ArtifactValidationError(message)


def _validate_columns_and_types(
    bundle: ArtifactBundle, schemas: Mapping[ArtifactName, pa.Schema]
) -> None:
    for artifact_name in ARTIFACT_NAMES:
        frame = bundle.table(artifact_name)
        schema = schemas[artifact_name]
        _require(
            list(frame.columns) == schema.names,
            f"{artifact_name} columns do not match schema: {list(frame.columns)}",
        )
        try:
            dataframe_to_arrow(frame, schema)
        except (pa.ArrowInvalid, pa.ArrowTypeError, ValueError, TypeError) as error:
            raise ArtifactValidationError(
                f"{artifact_name} values do not match the declared schema: {error}"
            ) from error


def _validate_catalogs(bundle: ArtifactBundle, config: GeneratorConfig) -> None:
    stores = bundle.table("stores.parquet")
    products = bundle.table("products.parquet")
    policies = bundle.table("store_products.parquet")

    _require(len(stores) == config.store_count, "store count does not match configuration")
    _require(stores["store_id"].is_unique, "store_id must be unique")
    _require(stores["store_code"].is_unique, "store_code must be unique")
    _require(len(products) == config.sku_count, "product count does not match configuration")
    _require(products["product_id"].is_unique, "product_id must be unique")
    _require(products["sku"].is_unique, "SKU must be globally unique")
    _require(bool((products["unit_cost"] >= 0).all()), "unit_cost must be nonnegative")
    _require(bool((products["unit_price"] >= 0).all()), "unit_price must be nonnegative")

    expected_policy_count = config.store_count * config.sku_count
    _require(len(policies) == expected_policy_count, "Store + SKU policy count is incorrect")
    _require(
        not policies.duplicated(["store_id", "product_id"]).any(),
        "Store + SKU policy keys must be unique",
    )
    _require(bool(policies["active"].all()), "all generated Store + SKU policies must be active")
    _require(bool((policies["lead_time_days"] >= 0).all()), "lead time must be nonnegative")
    _require(bool((policies["safety_stock"] >= 0).all()), "safety stock must be nonnegative")
    _require(bool((policies["reorder_point"] >= 0).all()), "reorder point must be nonnegative")
    _require(
        set(policies["store_id"]) <= set(stores["store_id"]), "policy references unknown store"
    )
    _require(
        set(policies["product_id"]) <= set(products["product_id"]),
        "policy references unknown product",
    )
    product_skus = products.set_index("product_id")["sku"]
    expected_skus = policies["product_id"].map(product_skus)
    _require(expected_skus.equals(policies["sku"]), "policy SKU does not match product catalog")


def _validate_demand(bundle: ArtifactBundle, config: GeneratorConfig) -> tuple[str, str]:
    demand = bundle.table("demand_history.parquet")
    products = bundle.table("products.parquet")
    stores = bundle.table("stores.parquet")
    expected_rows = config.store_count * config.sku_count * config.month_count
    _require(len(demand) == expected_rows, "demand row count is incorrect")
    _require(
        not demand.duplicated(["store_id", "product_id", "period_start"]).any(),
        "demand contains duplicate Store + SKU + Month records",
    )
    _require(not demand.isna().any().any(), "demand records must not contain missing values")
    _require(pd.api.types.is_integer_dtype(demand["demand_units"]), "demand_units must be integer")
    _require(bool((demand["demand_units"] >= 0).all()), "demand_units must be nonnegative")
    _require(set(demand["store_id"]) <= set(stores["store_id"]), "demand references unknown store")
    _require(
        set(demand["product_id"]) <= set(products["product_id"]),
        "demand references unknown product",
    )

    group_sizes = demand.groupby(["store_id", "product_id"], sort=False).size()
    _require(
        len(group_sizes) == config.store_count * config.sku_count,
        "demand does not contain every Store + SKU series",
    )
    _require(
        bool((group_sizes == config.month_count).all()),
        "every Store + SKU series must contain the configured month count",
    )
    expected_periods = set(
        pd.date_range(
            end=pd.Timestamp(config.end_period), periods=config.month_count, freq="MS"
        ).date
    )
    actual_periods = set(demand["period_start"])
    _require(
        actual_periods == expected_periods, "demand periods are not one continuous month range"
    )
    per_series_periods = demand.groupby(["store_id", "product_id"])["period_start"].nunique()
    _require(
        bool((per_series_periods == config.month_count).all()),
        "a Store + SKU series contains a missing month",
    )

    store_means = demand.groupby("store_id")["demand_units"].mean().round(6)
    _require(store_means.nunique() > 1, "stores must exhibit different demand behavior")
    return min(expected_periods).isoformat(), max(expected_periods).isoformat()


def _validate_inventory_and_truth(bundle: ArtifactBundle, config: GeneratorConfig) -> None:
    inventory = bundle.table("inventory_snapshots.parquet")
    truth = bundle.table("synthetic_ground_truth.parquet")
    policies = bundle.table("store_products.parquet")
    expected_series = config.store_count * config.sku_count

    _require(len(inventory) == expected_series, "inventory snapshot count is incorrect")
    _require(
        not inventory.duplicated(["store_id", "product_id"]).any(),
        "inventory snapshot keys must be unique",
    )
    for column in ("on_hand", "allocated", "on_order", "on_order_due_within_lead_time"):
        _require(bool((inventory[column] >= 0).all()), f"{column} must be nonnegative")
    _require(
        set(INVENTORY_SCENARIOS) <= set(inventory["inventory_scenario"]),
        "generated inventory must include every required scenario",
    )

    policy_values = policies.set_index(["store_id", "product_id"])[
        ["lead_time_days", "safety_stock"]
    ].sort_index()
    inventory_values = inventory.set_index(["store_id", "product_id"])[
        ["lead_time_days", "safety_stock"]
    ].sort_index()
    _require(
        policy_values.equals(inventory_values),
        "inventory planning values must match Store + SKU policies",
    )

    _require(len(truth) == expected_series, "ground-truth row count is incorrect")
    _require(
        not truth.duplicated(["store_id", "product_id"]).any(),
        "ground-truth keys must be unique",
    )
    _require(
        set(DEMAND_PATTERNS) <= set(truth["demand_pattern"]),
        "generated portfolio must include every required demand pattern",
    )


def _validate_timestamps(bundle: ArtifactBundle, config: GeneratorConfig) -> None:
    for artifact_name, frame in bundle.tables.items():
        created_at = pd.to_datetime(frame["created_at"], utc=True)
        _require(
            bool((created_at == config.generation_timestamp_utc).all()),
            f"{artifact_name} created_at must equal the pinned UTC generation timestamp",
        )


def validate_artifacts(
    bundle: ArtifactBundle,
    config: GeneratorConfig,
    schemas: Mapping[ArtifactName, pa.Schema],
) -> ValidationSummary:
    """Validate schema, referential, grain, completeness, and realism invariants."""

    _validate_columns_and_types(bundle, schemas)
    _validate_catalogs(bundle, config)
    period_start, period_end = _validate_demand(bundle, config)
    _validate_inventory_and_truth(bundle, config)
    _validate_timestamps(bundle, config)
    return ValidationSummary(
        row_counts={name: len(bundle.table(name)) for name in ARTIFACT_NAMES},
        period_start=period_start,
        period_end=period_end,
    )
