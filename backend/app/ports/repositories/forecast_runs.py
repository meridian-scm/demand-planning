"""Read contract for immutable forecast-run artifacts."""

from typing import Protocol

from app.domain import ForecastRun, ForecastSeriesResult, StoredForecast, StoredModelEvaluation


class ForecastRunReadRepository(Protocol):
    def list_runs(self) -> tuple[ForecastRun, ...]: ...

    def get_run(self, run_id: str) -> ForecastRun | None: ...

    def list_series(
        self,
        run_id: str,
        *,
        store_id: str | None,
        query: str,
        limit: int,
    ) -> tuple[ForecastSeriesResult, ...]: ...

    def get_evaluations(
        self, run_id: str, store_id: str, product_id: str
    ) -> tuple[StoredModelEvaluation, ...]: ...

    def get_forecasts(
        self, run_id: str, store_id: str, product_id: str
    ) -> tuple[StoredForecast, ...]: ...
