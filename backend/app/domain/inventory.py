"""Storage-independent inventory position and risk types."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

InventoryRiskClassification = Literal["stockout", "below_safety_stock", "healthy", "excess"]
InventoryRiskSeverity = Literal["info", "watch", "warning"]


@dataclass(frozen=True, slots=True)
class InventorySnapshot:
    """One current inventory position at the Store + SKU grain."""

    store_id: str
    product_id: str
    sku: str
    snapshot_at: datetime
    on_hand: int
    allocated: int
    on_order: int
    on_order_due_within_lead_time: int
    next_expected_receipt_at: datetime | None
    lead_time_days: int
    safety_stock: int

    def __post_init__(self) -> None:
        if not self.store_id or not self.product_id or not self.sku:
            raise ValueError("inventory identifiers must not be empty")
        if self.snapshot_at.tzinfo is None:
            raise ValueError("snapshot_at must be timezone-aware")
        if (
            self.next_expected_receipt_at is not None
            and self.next_expected_receipt_at.tzinfo is None
        ):
            raise ValueError("next_expected_receipt_at must be timezone-aware")
        quantities = (
            self.on_hand,
            self.allocated,
            self.on_order,
            self.on_order_due_within_lead_time,
            self.lead_time_days,
            self.safety_stock,
        )
        if any(value < 0 for value in quantities):
            raise ValueError("inventory quantities and policy values must be nonnegative")
        if self.on_order_due_within_lead_time > self.on_order:
            raise ValueError("on-order quantity due within lead time cannot exceed total on-order")


@dataclass(frozen=True, slots=True)
class InventoryRisk:
    """Projected inventory evidence at replenishment arrival."""

    risk_id: str
    store_id: str
    product_id: str
    sku: str
    classification: InventoryRiskClassification
    severity: InventoryRiskSeverity
    snapshot_at: datetime
    replenishment_arrival_at: datetime
    available_inventory: int
    on_order_due_within_lead_time: int
    forecast_demand_during_lead_time: float
    projected_inventory: float
    safety_stock: int
    coverage_months: float | None
    excess_coverage_threshold_months: float
    selected_model: str
    forecast_id: str
    training_cutoff: date
    forecast_horizon_months: int
