"""Application service for the Store + SKU Demand Explorer."""

from dataclasses import dataclass
from datetime import date
from statistics import fmean

from app.domain import DemandObservation, Product, StoreProduct
from app.ports.repositories.planning import PlanningReadRepository


class PlanningDataNotFoundError(LookupError):
    """Raised when the requested Store + SKU series does not exist."""


@dataclass(frozen=True, slots=True)
class DemandSummary:
    """Concise business summary derived from monthly observations."""

    period_start: date
    period_end: date
    total_units: int
    average_monthly_units: float
    minimum_monthly_units: int
    maximum_monthly_units: int
    zero_demand_months: int


@dataclass(frozen=True, slots=True)
class DemandSeries:
    """Planner-facing series and its catalog and policy context."""

    product: Product
    policy: StoreProduct
    observations: tuple[DemandObservation, ...]
    summary: DemandSummary


class DemandExplorerService:
    """Orchestrate planning-data retrieval and summary calculation."""

    def __init__(self, repository: PlanningReadRepository) -> None:
        self._repository = repository

    def get_series(self, store_id: str, product_id: str) -> DemandSeries:
        product = self._repository.get_product(product_id)
        policy = self._repository.get_store_product(store_id, product_id)
        observations = self._repository.get_demand_series(store_id, product_id)
        if product is None or policy is None or not observations:
            raise PlanningDataNotFoundError(
                f"No demand series exists for store {store_id!r} and product {product_id!r}."
            )

        units = [observation.demand_units for observation in observations]
        return DemandSeries(
            product=product,
            policy=policy,
            observations=observations,
            summary=DemandSummary(
                period_start=observations[0].period_start,
                period_end=observations[-1].period_start,
                total_units=sum(units),
                average_monthly_units=fmean(units),
                minimum_monthly_units=min(units),
                maximum_monthly_units=max(units),
                zero_demand_months=sum(unit == 0 for unit in units),
            ),
        )
