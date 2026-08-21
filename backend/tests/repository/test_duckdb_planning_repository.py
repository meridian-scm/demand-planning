"""Contract tests for the DuckDB + Parquet planning adapter."""

from pathlib import Path

from app.data_generation.artifacts import publish_artifacts
from app.data_generation.config import GeneratorConfig
from app.data_generation.generator import generate_artifacts
from app.infrastructure.duckdb import DuckDBPlanningRepository


def _repository(
    tmp_path: Path, generator_config: GeneratorConfig, project_root: Path
) -> DuckDBPlanningRepository:
    output = tmp_path / "test-v1"
    config = generator_config.model_copy(update={"output_directory": output})
    publish_artifacts(generate_artifacts(config), config, project_root)
    return DuckDBPlanningRepository(output)


def test_repository_reads_catalog_and_complete_series(
    tmp_path: Path, generator_config: GeneratorConfig, project_root: Path
) -> None:
    repository = _repository(tmp_path, generator_config, project_root)

    stores = repository.list_stores()
    products = repository.search_products(stores[0].store_id, "", limit=10)
    series = repository.get_demand_series(stores[0].store_id, products[0].product_id)
    inventory = repository.get_inventory_snapshot(stores[0].store_id, products[0].product_id)

    assert repository.is_ready()
    assert len(stores) == 5
    assert len(products) == 10
    assert len(series) == generator_config.month_count
    assert inventory is not None
    assert inventory.sku == products[0].sku
    assert inventory.on_order_due_within_lead_time <= inventory.on_order
    assert inventory.snapshot_at.tzinfo is not None
    assert tuple(point.period_start for point in series) == tuple(
        sorted(point.period_start for point in series)
    )


def test_product_search_is_store_scoped_and_case_insensitive(
    tmp_path: Path, generator_config: GeneratorConfig, project_root: Path
) -> None:
    repository = _repository(tmp_path, generator_config, project_root)
    store = repository.list_stores()[0]
    expected = repository.search_products(store.store_id, "", limit=1)[0]

    results = repository.search_products(store.store_id, expected.sku.lower(), limit=10)

    assert [product.product_id for product in results] == [expected.product_id]
