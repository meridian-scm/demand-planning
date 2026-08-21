"""Deterministic generation of realistic Store + SKU planning facts."""

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from hashlib import blake2b
from math import cos, pi, sqrt
from typing import cast

import numpy as np
import pandas as pd

from app.data_generation.config import DEMAND_PATTERNS, DemandPattern, GeneratorConfig
from app.data_generation.models import ArtifactBundle, ArtifactName

GENERATOR_VERSION = "0.1.0"


@dataclass(frozen=True, slots=True)
class StoreProfile:
    store_id: str
    store_code: str
    store_name: str
    city: str
    region: str
    country: str
    timezone: str
    volume_multiplier: float
    volatility_multiplier: float
    seasonal_multiplier: float
    preferred_category: str


@dataclass(frozen=True, slots=True)
class CategoryProfile:
    category: str
    subcategories: tuple[str, ...]
    brands: tuple[str, ...]
    products: tuple[str, ...]
    base_monthly_demand: float
    price_range: tuple[float, float]
    peak_month: int


@dataclass(frozen=True, slots=True)
class ProductRecord:
    product_id: str
    sku: str
    product_name: str
    category: str
    subcategory: str
    brand: str
    unit_cost: Decimal
    unit_price: Decimal
    created_at: datetime


@dataclass(frozen=True, slots=True)
class StoreProductRecord:
    store_id: str
    product_id: str
    sku: str
    active: bool
    lead_time_days: int
    safety_stock: int
    reorder_point: int
    minimum_order_quantity: int
    order_multiple: int
    service_level_target: float
    created_at: datetime


STORE_PROFILES: tuple[StoreProfile, ...] = (
    StoreProfile(
        "store-001",
        "TOR-01",
        "Toronto Central",
        "Toronto",
        "Ontario",
        "Canada",
        "America/Toronto",
        1.28,
        0.90,
        1.00,
        "Grocery",
    ),
    StoreProfile(
        "store-002",
        "VAN-01",
        "Vancouver Harbour",
        "Vancouver",
        "British Columbia",
        "Canada",
        "America/Vancouver",
        1.12,
        1.05,
        0.88,
        "Outdoor & Seasonal",
    ),
    StoreProfile(
        "store-003",
        "MTL-01",
        "Montréal Marché",
        "Montréal",
        "Quebec",
        "Canada",
        "America/Toronto",
        1.05,
        1.00,
        1.08,
        "Home & Kitchen",
    ),
    StoreProfile(
        "store-004",
        "CAL-01",
        "Calgary West",
        "Calgary",
        "Alberta",
        "Canada",
        "America/Edmonton",
        0.92,
        1.18,
        1.24,
        "Outdoor & Seasonal",
    ),
    StoreProfile(
        "store-005",
        "HAL-01",
        "Halifax Waterfront",
        "Halifax",
        "Nova Scotia",
        "Canada",
        "America/Halifax",
        0.74,
        1.12,
        1.12,
        "Health & Personal Care",
    ),
)

CATEGORY_PROFILES: tuple[CategoryProfile, ...] = (
    CategoryProfile(
        "Grocery",
        ("Coffee & Tea", "Pantry", "Snacks"),
        ("Northstar", "Harbour House", "Field & Mill"),
        ("Whole Bean Coffee", "Herbal Tea", "Granola", "Trail Mix"),
        82.0,
        (5.99, 24.99),
        12,
    ),
    CategoryProfile(
        "Home & Kitchen",
        ("Cookware", "Storage", "Tabletop"),
        ("Hearthline", "Cedar & Stone", "Meridian Home"),
        ("Storage Set", "Serving Bowl", "Kitchen Towel", "Stock Pot"),
        45.0,
        (12.99, 89.99),
        11,
    ),
    CategoryProfile(
        "Health & Personal Care",
        ("Wellness", "Skin Care", "Personal Care"),
        ("True North", "Everwell", "Clearwater"),
        ("Daily Moisturizer", "Mineral Bath Salts", "Hand Care Set", "Vitamin Blend"),
        58.0,
        (8.99, 49.99),
        1,
    ),
    CategoryProfile(
        "Outdoor & Seasonal",
        ("Camping", "Garden", "Weather Essentials"),
        ("Ridgeline", "Coastal Trail", "Wildwood"),
        ("Insulated Bottle", "Camp Lantern", "Garden Tool Set", "Rain Poncho"),
        34.0,
        (14.99, 129.99),
        7,
    ),
    CategoryProfile(
        "Office & Technology",
        ("Desk Essentials", "Accessories", "Organization"),
        ("Paperline", "Circuit North", "Workwell"),
        ("Notebook Set", "Charging Cable", "Desk Organizer", "Wireless Mouse"),
        39.0,
        (6.99, 79.99),
        9,
    ),
    CategoryProfile(
        "Pet Care",
        ("Food", "Treats", "Accessories"),
        ("Good Companion", "Maple Paws", "Harbour Pet"),
        ("Dry Food", "Training Treats", "Travel Bowl", "Grooming Brush"),
        51.0,
        (7.99, 69.99),
        3,
    ),
)

INVENTORY_SCENARIOS: tuple[str, ...] = (
    "healthy",
    "low_stock",
    "potential_stockout",
    "excess_inventory",
    "high_demand_insufficient_inventory",
    "incoming_inventory",
)


def _seed_for(config: GeneratorConfig, namespace: str, *keys: str) -> int:
    payload = "|".join((str(config.random_seed), namespace, *keys)).encode()
    return int.from_bytes(blake2b(payload, digest_size=8).digest(), "big")


def _rng_for(config: GeneratorConfig, namespace: str, *keys: str) -> np.random.Generator:
    return np.random.default_rng(_seed_for(config, namespace, *keys))


def _money(value: float) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _product_scale(config: GeneratorConfig, product_id: str) -> float:
    return float(_rng_for(config, "product-scale", product_id).uniform(0.55, 1.65))


def _category_profile(category: str) -> CategoryProfile:
    return next(profile for profile in CATEGORY_PROFILES if profile.category == category)


def _series_baseline(
    config: GeneratorConfig,
    store: StoreProfile,
    product: ProductRecord,
) -> float:
    category = _category_profile(product.category)
    preference = 1.22 if store.preferred_category == product.category else 1.0
    return (
        category.base_monthly_demand
        * store.volume_multiplier
        * preference
        * _product_scale(config, product.product_id)
    )


def _generate_stores(config: GeneratorConfig) -> tuple[tuple[StoreProfile, ...], pd.DataFrame]:
    stores = STORE_PROFILES[: config.store_count]
    records = [
        {
            "store_id": store.store_id,
            "store_code": store.store_code,
            "store_name": store.store_name,
            "city": store.city,
            "region": store.region,
            "country": store.country,
            "timezone": store.timezone,
            "created_at": config.generation_timestamp_utc,
        }
        for store in stores
    ]
    return stores, pd.DataFrame.from_records(records)


def _generate_products(config: GeneratorConfig) -> tuple[tuple[ProductRecord, ...], pd.DataFrame]:
    products: list[ProductRecord] = []
    for product_number in range(1, config.sku_count + 1):
        profile = CATEGORY_PROFILES[(product_number - 1) % len(CATEGORY_PROFILES)]
        rng = _rng_for(config, "product", f"product-{product_number:05d}")
        subcategory = profile.subcategories[int(rng.integers(len(profile.subcategories)))]
        brand = profile.brands[int(rng.integers(len(profile.brands)))]
        descriptor = profile.products[int(rng.integers(len(profile.products)))]
        variant = int(rng.integers(1, 100))
        unit_price = _money(float(rng.uniform(*profile.price_range)))
        margin = Decimal(str(float(rng.uniform(0.28, 0.52))))
        unit_cost = (unit_price * (Decimal("1") - margin)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        products.append(
            ProductRecord(
                product_id=f"product-{product_number:05d}",
                sku=f"SKU-{product_number:05d}",
                product_name=f"{brand} {descriptor} {variant:02d}",
                category=profile.category,
                subcategory=subcategory,
                brand=brand,
                unit_cost=unit_cost,
                unit_price=unit_price,
                created_at=config.generation_timestamp_utc,
            )
        )
    return tuple(products), pd.DataFrame.from_records([asdict(product) for product in products])


def _generate_store_products(
    config: GeneratorConfig,
    stores: tuple[StoreProfile, ...],
    products: tuple[ProductRecord, ...],
) -> tuple[dict[tuple[str, str], StoreProductRecord], pd.DataFrame]:
    policies: dict[tuple[str, str], StoreProductRecord] = {}
    for store in stores:
        for product in products:
            rng = _rng_for(config, "planning-policy", store.store_id, product.product_id)
            baseline = _series_baseline(config, store, product)
            lead_time = int(rng.choice(np.array([7, 14, 21, 30, 45, 60], dtype=np.int32)))
            service_level = float(rng.choice(np.array([0.90, 0.95, 0.97, 0.99])))
            service_factor = {0.90: 0.8, 0.95: 1.0, 0.97: 1.2, 0.99: 1.5}[service_level]
            safety_stock = max(1, round(baseline * sqrt(lead_time / 30) * 0.35 * service_factor))
            lead_time_demand = round(baseline * lead_time / 30)
            order_multiple = int(rng.choice(np.array([1, 5, 10, 12, 24], dtype=np.int32)))
            minimum_order_quantity = order_multiple * int(rng.integers(1, 5))
            policy = StoreProductRecord(
                store_id=store.store_id,
                product_id=product.product_id,
                sku=product.sku,
                active=True,
                lead_time_days=lead_time,
                safety_stock=safety_stock,
                reorder_point=lead_time_demand + safety_stock,
                minimum_order_quantity=minimum_order_quantity,
                order_multiple=order_multiple,
                service_level_target=service_level,
                created_at=config.generation_timestamp_utc,
            )
            policies[(store.store_id, product.product_id)] = policy
    return policies, pd.DataFrame.from_records([asdict(policy) for policy in policies.values()])


def _select_pattern(config: GeneratorConfig, store_id: str, product_id: str) -> DemandPattern:
    rng = _rng_for(config, "demand-pattern", store_id, product_id)
    probabilities = np.array([config.pattern_weights[pattern] for pattern in DEMAND_PATTERNS])
    selected = str(rng.choice(np.array(DEMAND_PATTERNS), p=probabilities))
    return cast(DemandPattern, selected)


def _pattern_components(
    pattern: DemandPattern,
    index: int,
    length: int,
    event_index: int,
) -> tuple[float, float, str, str | None]:
    progress = index / max(1, length - 1)
    if pattern == "growing":
        return 0.65 + 0.85 * progress, 0.10, "growth", None
    if pattern == "declining":
        return 1.45 - 0.75 * progress, 0.10, "decline", None
    if pattern == "seasonal":
        return 1.0, 0.24, "mature", None
    if pattern == "strong_seasonal":
        return 1.0, 0.52, "mature", None
    if pattern == "volatile":
        return 1.0, 0.10, "mature", None
    if pattern == "intermittent":
        return 0.55, 0.08, "low_volume", None
    if pattern == "spike":
        return (3.6 if index == event_index else 1.0), 0.10, "mature", "spike"
    if pattern == "drop":
        return (0.12 if index == event_index else 1.0), 0.10, "mature", "drop"
    if pattern == "new_product":
        ramp_start = 0.55
        ramp = 0.12 if progress < ramp_start else 0.12 + 0.88 * (progress - ramp_start) / 0.45
        return ramp, 0.08, "new_product", None
    if pattern == "mature":
        return 1.08 - 0.12 * progress, 0.08, "mature", None
    return 1.0, 0.08, "mature", None


def _generate_demand(
    config: GeneratorConfig,
    stores: tuple[StoreProfile, ...],
    products: tuple[ProductRecord, ...],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[tuple[str, str], float]]:
    periods = list(
        pd.date_range(
            end=pd.Timestamp(config.end_period), periods=config.month_count, freq="MS"
        ).date
    )
    demand_records: list[dict[str, object]] = []
    truth_records: list[dict[str, object]] = []
    recent_demand: dict[tuple[str, str], float] = {}

    for store in stores:
        for product in products:
            rng = _rng_for(config, "demand-series", store.store_id, product.product_id)
            pattern = _select_pattern(config, store.store_id, product.product_id)
            category = _category_profile(product.category)
            baseline = _series_baseline(config, store, product)
            event_index = int(rng.integers(max(1, config.month_count // 2), config.month_count))
            volatility = 0.12 * store.volatility_multiplier
            if pattern == "volatile":
                volatility = 0.42 * store.volatility_multiplier
            series_values: list[int] = []
            event_type: str | None = None

            for index, period in enumerate(periods):
                pattern_factor, seasonal_strength, lifecycle, possible_event = _pattern_components(
                    pattern, index, config.month_count, event_index
                )
                category_season = 1 + seasonal_strength * cos(
                    2 * pi * ((period.month - category.peak_month) % 12) / 12
                )
                store_season = 1 + 0.06 * store.seasonal_multiplier * cos(
                    2 * pi * ((period.month - ((category.peak_month + 1) % 12 or 12)) % 12) / 12
                )
                expected = max(0.0, baseline * pattern_factor * category_season * store_season)
                if pattern == "intermittent" and float(rng.random()) < 0.64:
                    demand_units = 0
                else:
                    noise = max(0.05, 1 + float(rng.normal(0, volatility)))
                    demand_units = int(rng.poisson(max(0.0, expected * noise)))
                series_values.append(demand_units)
                demand_records.append(
                    {
                        "store_id": store.store_id,
                        "product_id": product.product_id,
                        "sku": product.sku,
                        "period_start": period,
                        "demand_units": demand_units,
                        "created_at": config.generation_timestamp_utc,
                    }
                )
                if possible_event is not None and index == event_index:
                    event_type = possible_event

            recent_demand[(store.store_id, product.product_id)] = float(
                np.mean(series_values[-min(3, len(series_values)) :])
            )
            _, seasonality_strength, lifecycle, _ = _pattern_components(
                pattern, config.month_count - 1, config.month_count, event_index
            )
            truth_records.append(
                {
                    "store_id": store.store_id,
                    "product_id": product.product_id,
                    "sku": product.sku,
                    "demand_pattern": pattern,
                    "lifecycle": lifecycle,
                    "seasonality_strength": seasonality_strength,
                    "volatility_scale": volatility,
                    "event_type": event_type,
                    "event_period_start": periods[event_index] if event_type else None,
                    "created_at": config.generation_timestamp_utc,
                }
            )

    return (
        pd.DataFrame.from_records(demand_records),
        pd.DataFrame.from_records(truth_records),
        recent_demand,
    )


def _generate_inventory(
    config: GeneratorConfig,
    stores: tuple[StoreProfile, ...],
    products: tuple[ProductRecord, ...],
    policies: dict[tuple[str, str], StoreProductRecord],
    recent_demand: dict[tuple[str, str], float],
) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for store in stores:
        for product in products:
            key = (store.store_id, product.product_id)
            policy = policies[key]
            monthly_demand = recent_demand[key]
            lead_demand = monthly_demand * policy.lead_time_days / 30
            rng = _rng_for(config, "inventory", *key)
            allocated = max(0, round(monthly_demand * float(rng.uniform(0.05, 0.20))))
            scenario = INVENTORY_SCENARIOS[_seed_for(config, "inventory-scenario", *key) % 6]
            on_order_due = 0
            later_on_order = 0

            if scenario == "healthy":
                on_hand = round(allocated + lead_demand + 1.4 * policy.safety_stock)
            elif scenario == "low_stock":
                on_hand = round(allocated + lead_demand + 0.45 * policy.safety_stock)
            elif scenario == "potential_stockout":
                on_hand = max(0, round(allocated + 0.35 * lead_demand))
            elif scenario == "excess_inventory":
                on_hand = round(allocated + lead_demand + policy.safety_stock + 6 * monthly_demand)
            elif scenario == "high_demand_insufficient_inventory":
                on_hand = max(0, round(allocated + 0.20 * lead_demand))
            else:
                on_hand = max(0, round(allocated + 0.25 * lead_demand))
                on_order_due = round(0.9 * lead_demand + 1.3 * policy.safety_stock)
                later_on_order = round(monthly_demand)

            on_order = on_order_due + later_on_order
            receipt_at = (
                config.generation_timestamp_utc + timedelta(days=max(1, policy.lead_time_days // 2))
                if on_order > 0
                else None
            )
            records.append(
                {
                    "store_id": store.store_id,
                    "product_id": product.product_id,
                    "sku": product.sku,
                    "snapshot_at": config.generation_timestamp_utc,
                    "on_hand": on_hand,
                    "allocated": allocated,
                    "on_order": on_order,
                    "on_order_due_within_lead_time": on_order_due,
                    "next_expected_receipt_at": receipt_at,
                    "lead_time_days": policy.lead_time_days,
                    "safety_stock": policy.safety_stock,
                    "inventory_scenario": scenario,
                    "created_at": config.generation_timestamp_utc,
                }
            )
    return pd.DataFrame.from_records(records)


def generate_artifacts(config: GeneratorConfig) -> ArtifactBundle:
    """Generate all logical records without writing or mutating storage."""

    stores, stores_frame = _generate_stores(config)
    products, products_frame = _generate_products(config)
    policies, policies_frame = _generate_store_products(config, stores, products)
    demand_frame, truth_frame, recent_demand = _generate_demand(config, stores, products)
    inventory_frame = _generate_inventory(config, stores, products, policies, recent_demand)
    tables: dict[ArtifactName, pd.DataFrame] = {
        "stores.parquet": stores_frame,
        "products.parquet": products_frame,
        "store_products.parquet": policies_frame,
        "demand_history.parquet": demand_frame,
        "inventory_snapshots.parquet": inventory_frame,
        "synthetic_ground_truth.parquet": truth_frame,
    }
    return ArtifactBundle(tables=tables)
