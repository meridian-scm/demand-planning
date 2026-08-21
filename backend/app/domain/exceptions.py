"""Planning-exception domain types and lifecycle rules."""

from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Literal

ExceptionType = Literal[
    "potential_stockout",
    "below_safety_stock",
    "excess_inventory",
    "demand_spike",
    "demand_decline",
    "forecast_uncertainty",
    "forecast_bias",
]
ExceptionSeverity = Literal["medium", "high", "critical"]
ExceptionStatus = Literal["open", "acknowledged", "resolved", "dismissed"]
ExceptionEvidenceValue = str | int | float

_ALLOWED_TRANSITIONS: dict[ExceptionStatus, frozenset[ExceptionStatus]] = {
    "open": frozenset(("acknowledged", "dismissed")),
    "acknowledged": frozenset(("resolved", "dismissed")),
    "resolved": frozenset(),
    "dismissed": frozenset(),
}


@dataclass(frozen=True, slots=True)
class PlanningException:
    """A prioritized planner decision with traceable evidence."""

    exception_id: str
    store_id: str
    product_id: str
    sku: str
    exception_type: ExceptionType
    severity: ExceptionSeverity
    priority_score: int
    status: ExceptionStatus
    relevant_period: date
    title: str
    description: str
    metric_name: str
    metric_value: float
    threshold_value: float
    evidence: dict[str, ExceptionEvidenceValue]
    related_signal_id: str | None
    related_risk_id: str | None
    related_forecast_id: str | None
    created_at: datetime

    def transition_to(self, status: ExceptionStatus) -> "PlanningException":
        """Apply the intentionally small MVP lifecycle without persistence concerns."""

        if status not in _ALLOWED_TRANSITIONS[self.status]:
            raise ValueError(f"Cannot transition an exception from {self.status!r} to {status!r}.")
        return replace(self, status=status)
