"""Explainable demand signals at the Store + SKU grain."""

from dataclasses import dataclass
from datetime import date
from typing import Literal

SignalType = Literal["trend", "volatility", "seasonality", "anomaly"]
SignalDirection = Literal["growing", "declining", "stable", "volatile", "seasonal", "spike", "drop"]
SignalSeverity = Literal["info", "watch", "warning"]
EvidenceValue = str | int | float


@dataclass(frozen=True, slots=True)
class DemandSignal:
    """A planner-facing signal with the evidence that triggered it."""

    signal_id: str
    store_id: str
    product_id: str
    sku: str
    signal_type: SignalType
    direction: SignalDirection
    severity: SignalSeverity
    period_start: date | None
    title: str
    description: str
    metric_name: str
    metric_value: float
    baseline_value: float | None
    threshold_value: float
    evidence: dict[str, EvidenceValue]
