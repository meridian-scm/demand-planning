"""Deterministic dummy-data generator for demos, dev environments and tests.

Produces a realistic, self-consistent planning dataset: products across a few
categories, locations, 24 months of monthly sales history with trend and
seasonality baked in, current inventory positions, and — deliberately — a
handful of SKUs engineered to trip each exception rule, so the exception
dashboard is never empty on a fresh install.

Everything is seeded from a single ``random.Random(seed)`` instance, so the
same seed always produces byte-identical data. That determinism is what lets
the integration test suite assert on generated fixtures.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.models import InventorySnapshot, Location, Product, SalesHistory
from app.services.forecasting.engine import add_months, normalise_period

DEFAULT_SEED = 20240601
HISTORY_MONTHS = 24

_CATEGORIES = {
    "Beverages": ["Sparkling Water", "Cold Brew Coffee", "Herbal Tea", "Sports Drink", "Orange Juice"],
    "Snacks": ["Trail Mix", "Granola Bar", "Pretzel Bag", "Popcorn Pack", "Rice Crackers"],
    "Household": ["Paper Towels", "Dish Soap", "Laundry Pods", "All-Purpose Cleaner", "Trash Bags"],
    "Personal Care": ["Shampoo", "Body Wash", "Toothpaste", "Hand Lotion", "Deodorant"],
    "Electronics Accessories": ["USB-C Cable", "Wireless Mouse", "Phone Case", "Power Bank", "Earbuds"],
}

_LOCATIONS = [
    ("DC-EAST", "East Distribution Center", "Northeast", "USA"),
    ("DC-WEST", "West Distribution Center", "West", "USA"),
    ("DC-CENTRAL", "Central Distribution Center", "Midwest", "USA"),
]


@dataclass(slots=True)
class SeedSummary:
    """Counts of what was created, returned to the caller / CLI for logging."""

    locations: int = 0
    products: int = 0
    sales_rows: int = 0
    inventory_rows: int = 0
    scenarios: dict[str, str] | None = None


def _monthly_periods(end: date, months: int) -> list[date]:
    anchor = normalise_period(end)
    return [add_months(anchor, offset - months + 1) for offset in range(months)]


def _seasonal_multiplier(period: date, amplitude: float, phase_month: int) -> float:
    """A smooth yearly cycle peaking in ``phase_month``."""
    import math

    angle = 2 * math.pi * ((period.month - phase_month) % 12) / 12
    return 1.0 + amplitude * math.cos(angle)


def _baseline_series(
    rng: random.Random,
    periods: list[date],
    *,
    base_level: float,
    monthly_growth_pct: float,
    seasonal_amplitude: float,
    phase_month: int,
    noise_pct: float,
) -> list[int]:
    """Trend + seasonality + noise, floored at zero and rounded to whole units."""
    values: list[int] = []
    level = base_level
    for _index, period in enumerate(periods):
        level *= 1 + monthly_growth_pct / 100.0
        seasonal = _seasonal_multiplier(period, seasonal_amplitude, phase_month)
        noise = 1 + rng.gauss(0, noise_pct)
        values.append(max(0, round(level * seasonal * noise)))
    return values


class DataSeeder:
    """Builds and inserts a full demo dataset."""

    def __init__(self, db: Session, *, seed: int = DEFAULT_SEED, as_of: date | None = None) -> None:
        self.db = db
        self.rng = random.Random(seed)
        self.as_of = as_of or date.today()

    def run(self) -> SeedSummary:
        summary = SeedSummary(scenarios={})
        locations = self._create_locations()
        summary.locations = len(locations)

        periods = _monthly_periods(self.as_of, HISTORY_MONTHS)
        products = self._create_products()
        summary.products = len(products)

        sales_rows = 0
        for product, profile in products:
            values = _baseline_series(
                self.rng,
                periods,
                base_level=profile["base_level"],
                monthly_growth_pct=profile["growth_pct"],
                seasonal_amplitude=profile["seasonal_amplitude"],
                phase_month=profile["phase_month"],
                noise_pct=profile["noise_pct"],
            )
            values = profile["adjust"](values, periods, self.rng) if profile.get("adjust") else values

            history_start = len(periods) - profile.get("history_months", len(periods))
            for offset, (period, units) in enumerate(zip(periods, values, strict=True)):
                if offset < history_start:
                    continue
                location = locations[offset % len(locations)] if profile.get("multi_location") else None
                self.db.add(
                    SalesHistory(
                        product_id=product.id,
                        location_id=location.id if location else None,
                        period_start=period,
                        units_sold=units,
                        revenue=round(units * float(product.unit_price or 0), 2)
                        if product.unit_price
                        else None,
                        source="seed",
                    )
                )
                sales_rows += 1

            self._create_inventory(product, values, profile)
            if profile.get("scenario"):
                summary.scenarios[product.sku] = profile["scenario"]

        self.db.commit()
        summary.sales_rows = sales_rows
        summary.inventory_rows = len(products)
        return summary

    # ------------------------------------------------------------------ #
    def _create_locations(self) -> list[Location]:
        rows = []
        for code, name, region, country in _LOCATIONS:
            row = Location(code=code, name=name, region=region, country=country)
            self.db.add(row)
            rows.append(row)
        self.db.flush()
        return rows

    def _create_products(self) -> list[tuple[Product, dict]]:
        products: list[tuple[Product, dict]] = []
        sku_counter = 1000

        for category, names in _CATEGORIES.items():
            for name in names:
                sku_counter += 1
                sku = f"SKU-{sku_counter}"
                base_level = self.rng.uniform(80, 400)
                unit_cost = round(self.rng.uniform(2, 40), 2)
                unit_price = round(unit_cost * self.rng.uniform(1.3, 2.2), 2)

                profile = {
                    "base_level": base_level,
                    "growth_pct": self.rng.uniform(-0.5, 1.5),
                    "seasonal_amplitude": self.rng.uniform(0.05, 0.25),
                    "phase_month": self.rng.randint(1, 12),
                    "noise_pct": self.rng.uniform(0.05, 0.15),
                    "history_months": HISTORY_MONTHS,
                    "multi_location": self.rng.random() < 0.3,
                }

                product = Product(
                    sku=sku,
                    name=f"{name}",
                    category=category,
                    subcategory=None,
                    unit_of_measure="EA",
                    unit_cost=unit_cost,
                    unit_price=unit_price,
                    lead_time_days=self.rng.choice([14, 21, 30, 45, 60]),
                    safety_stock_units=self.rng.randint(20, 100),
                )
                self.db.add(product)
                products.append((product, profile))

        self.db.flush()
        self._engineer_scenarios(products)
        return products

    def _engineer_scenarios(self, products: list[tuple[Product, dict]]) -> None:
        """Bend a handful of profiles so every exception rule has a real example."""

        def spike(values: list[int], periods: list[date], rng: random.Random) -> list[int]:
            values = list(values)
            values[-1] = round(values[-2] * rng.uniform(1.4, 1.8))
            return values

        def drop(values: list[int], periods: list[date], rng: random.Random) -> list[int]:
            values = list(values)
            values[-1] = round(values[-2] * rng.uniform(0.2, 0.5))
            return values

        def volatile(values: list[int], periods: list[date], rng: random.Random) -> list[int]:
            return [max(0, round(v * rng.uniform(0.2, 2.2))) for v in values]

        # Product 0: demand spike (household paper towels — plausible panic-buy)
        products[10][1]["adjust"] = spike
        products[10][1]["scenario"] = "demand_spike"

        # Product: demand drop
        products[15][1]["adjust"] = drop
        products[15][1]["scenario"] = "demand_drop"

        # Product: new / volatile — only 4 months of history
        products[20][1]["history_months"] = 4
        products[20][1]["adjust"] = volatile
        products[20][1]["scenario"] = "new_product_volatility"

        # Product: engineered for a weak, high-error forecast
        products[22][1]["adjust"] = volatile
        products[22][1]["noise_pct"] = 0.6
        products[22][1]["scenario"] = "forecast_anomaly"

    def _create_inventory(self, product: Product, values: list[int], profile: dict) -> None:
        recent_demand = values[-3:] if len(values) >= 3 else values
        average_demand = sum(recent_demand) / max(1, len(recent_demand))

        scenario = profile.get("scenario")
        if scenario == "demand_spike":
            cover_periods = self.rng.uniform(0.2, 0.5)  # engineered stockout risk
        elif scenario == "demand_drop":
            cover_periods = self.rng.uniform(5.0, 8.0)  # engineered excess inventory
        else:
            cover_periods = self.rng.uniform(1.5, 3.5)  # healthy cover

        on_hand = max(0, round(average_demand * cover_periods))
        self.db.add(
            InventorySnapshot(
                product_id=product.id,
                location_id=None,
                snapshot_date=self.as_of,
                on_hand_units=on_hand,
                on_order_units=round(average_demand * self.rng.uniform(0, 0.5)),
                allocated_units=round(on_hand * self.rng.uniform(0, 0.1)),
            )
        )


def seed_database(db: Session, *, seed: int = DEFAULT_SEED, as_of: date | None = None) -> SeedSummary:
    """Convenience entry point used by the CLI script and the test fixtures."""
    return DataSeeder(db, seed=seed, as_of=as_of).run()
