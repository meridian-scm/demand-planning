"""Determinism, grain, realism, and keyed-randomness tests."""

import pandas as pd
from app.data_generation.config import DEMAND_PATTERNS, GeneratorConfig
from app.data_generation.generator import INVENTORY_SCENARIOS, generate_artifacts
from app.data_generation.models import ARTIFACT_NAMES


def test_generator_creates_complete_realistic_test_profile(
    generator_config: GeneratorConfig,
) -> None:
    bundle = generate_artifacts(generator_config)
    stores = bundle.table("stores.parquet")
    products = bundle.table("products.parquet")
    policies = bundle.table("store_products.parquet")
    demand = bundle.table("demand_history.parquet")
    inventory = bundle.table("inventory_snapshots.parquet")
    truth = bundle.table("synthetic_ground_truth.parquet")

    assert len(stores) == 5
    assert len(products) == 24
    assert products["sku"].is_unique
    assert len(policies) == 120
    assert len(demand) == 7200
    assert len(inventory) == 120
    assert len(truth) == 120
    assert demand.groupby(["store_id", "product_id"]).size().eq(60).all()
    assert demand["period_start"].min().isoformat() == "2021-01-01"
    assert demand["period_start"].max().isoformat() == "2025-12-01"
    assert (demand["demand_units"] >= 0).all()
    assert (demand["demand_units"] == 0).any()
    assert set(DEMAND_PATTERNS) <= set(truth["demand_pattern"])
    assert set(INVENTORY_SCENARIOS) <= set(inventory["inventory_scenario"])


def test_generator_is_logically_reproducible(generator_config: GeneratorConfig) -> None:
    first = generate_artifacts(generator_config)
    second = generate_artifacts(generator_config)

    for artifact_name in ARTIFACT_NAMES:
        pd.testing.assert_frame_equal(first.table(artifact_name), second.table(artifact_name))


def test_adding_a_product_does_not_change_existing_series(
    generator_config: GeneratorConfig,
) -> None:
    original = generate_artifacts(generator_config)
    expanded = generate_artifacts(generator_config.model_copy(update={"sku_count": 25}))
    original_history = original.table("demand_history.parquet")
    expanded_history = expanded.table("demand_history.parquet")
    original_demand = original_history[
        (original_history["store_id"] == "store-001")
        & (original_history["product_id"] == "product-00001")
    ]
    expanded_demand = expanded_history[
        (expanded_history["store_id"] == "store-001")
        & (expanded_history["product_id"] == "product-00001")
    ]

    pd.testing.assert_frame_equal(
        original_demand.reset_index(drop=True), expanded_demand.reset_index(drop=True)
    )
