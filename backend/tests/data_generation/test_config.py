"""Generation-profile contract tests."""

from pathlib import Path

import pytest
from app.data_generation.config import GeneratorConfig, load_generator_config
from pydantic import ValidationError


def test_test_profile_is_small_but_keeps_five_stores(
    generator_config: GeneratorConfig,
) -> None:
    assert generator_config.profile == "test"
    assert generator_config.store_count == 5
    assert generator_config.sku_count == 24
    assert generator_config.month_count == 60
    assert (
        generator_config.store_count * generator_config.sku_count * generator_config.month_count
        == 7200
    )


def test_reference_profile_defines_the_exact_approved_scale(project_root: Path) -> None:
    config = load_generator_config(project_root / "config/data/reference.yaml")

    assert config.profile == "reference"
    assert config.store_count == 5
    assert config.sku_count == 3500
    assert config.month_count == 60
    assert config.store_count * config.sku_count * config.month_count == 1_050_000


def test_configuration_rejects_incomplete_pattern_weights(
    generator_config: GeneratorConfig,
) -> None:
    invalid_weights = dict(generator_config.pattern_weights)
    invalid_weights.pop("stable")

    with pytest.raises(ValidationError, match="every supported demand pattern"):
        GeneratorConfig.model_validate(
            {**generator_config.model_dump(), "pattern_weights": invalid_weights}
        )
