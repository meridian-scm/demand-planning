"""Read contract for portfolio overview inputs."""

from typing import Protocol

from app.domain.overview import OverviewDemandPoint, OverviewSeriesEvidence


class OverviewReadRepository(Protocol):
    """Retrieve bounded aggregate inputs without exposing storage implementation."""

    def get_timeline(
        self, run_id: str, *, store_id: str | None
    ) -> tuple[OverviewDemandPoint, ...]: ...

    def get_series_evidence(
        self, run_id: str, *, store_id: str | None
    ) -> tuple[OverviewSeriesEvidence, ...]: ...
