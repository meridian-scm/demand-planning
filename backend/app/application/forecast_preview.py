"""Stateless single-series forecast-preview orchestration."""

from dataclasses import dataclass

from app.application.demand_explorer import PlanningDataNotFoundError
from app.application.forecasting import ForecastingEngine
from app.domain import Product
from app.domain.forecasting import ForecastResult
from app.ports.repositories.planning import PlanningReadRepository


class ForecastPreviewLimitError(ValueError):
    """Raised when a preview exceeds the configured public-runtime limit."""


@dataclass(frozen=True, slots=True)
class ForecastPreview:
    """Forecast output with planner-facing Store + SKU identity."""

    store_id: str
    product: Product
    result: ForecastResult


class ForecastPreviewService:
    """Load one series and execute a bounded, non-persistent forecast."""

    def __init__(
        self,
        repository: PlanningReadRepository,
        engine: ForecastingEngine,
        *,
        maximum_horizon: int,
    ) -> None:
        self._repository = repository
        self._engine = engine
        self._maximum_horizon = maximum_horizon

    def create(
        self,
        store_id: str,
        product_id: str,
        *,
        horizon_months: int,
        interval_level: int,
    ) -> ForecastPreview:
        if horizon_months > self._maximum_horizon:
            raise ForecastPreviewLimitError(
                f"Forecast horizon exceeds the configured {self._maximum_horizon}-month limit."
            )
        product = self._repository.get_product(product_id)
        observations = self._repository.get_demand_series(store_id, product_id)
        if product is None or not observations:
            raise PlanningDataNotFoundError(
                f"No demand series exists for store {store_id!r} and product {product_id!r}."
            )
        result = self._engine.run(
            [observation.demand_units for observation in observations],
            training_cutoff=observations[-1].period_start,
            horizon=horizon_months,
            interval_level=interval_level,
        )
        return ForecastPreview(store_id=store_id, product=product, result=result)
