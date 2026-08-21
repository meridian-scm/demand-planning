"""Demand entities at the Store + SKU + Month planning grain."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class DemandObservation:
    """One completed monthly demand observation."""

    store_id: str
    product_id: str
    sku: str
    period_start: date
    demand_units: int

    def __post_init__(self) -> None:
        if not self.store_id or not self.product_id or not self.sku:
            raise ValueError("demand identifiers must not be empty")
        if self.period_start.day != 1:
            raise ValueError("period_start must be the first day of a month")
        if self.demand_units < 0:
            raise ValueError("demand_units must be nonnegative")
