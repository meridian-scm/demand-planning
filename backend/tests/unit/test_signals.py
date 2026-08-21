"""Unit tests for explainable demand-signal rules."""

from datetime import date

from app.application.signals import detect_demand_signals
from app.domain import DemandObservation


def _observations(values: list[int]) -> tuple[DemandObservation, ...]:
    observations = []
    for index, value in enumerate(values):
        year = 2021 + index // 12
        month = index % 12 + 1
        observations.append(
            DemandObservation(
                store_id="store-001",
                product_id="product-00001",
                sku="SKU-00001",
                period_start=date(year, month, 1),
                demand_units=value,
            )
        )
    return tuple(observations)


def _direction(values: list[int], signal_type: str) -> str:
    signals = detect_demand_signals(_observations(values))
    return next(signal.direction for signal in signals if signal.signal_type == signal_type)


def test_trend_rule_distinguishes_growth_decline_and_stability() -> None:
    assert _direction([20 + 2 * index for index in range(60)], "trend") == "growing"
    assert _direction([200 - 2 * index for index in range(60)], "trend") == "declining"
    assert _direction([100] * 60, "trend") == "stable"


def test_volatility_and_annual_seasonality_are_detected_with_evidence() -> None:
    volatile = detect_demand_signals(_observations([30, 170] * 30))
    volatility = next(signal for signal in volatile if signal.signal_type == "volatility")
    assert volatility.direction == "volatile"
    assert volatility.evidence["robust_dispersion_ratio"] == volatility.metric_value

    yearly_pattern = [100, 110, 120, 130, 140, 150, 140, 130, 120, 110, 100, 90]
    seasonal = detect_demand_signals(_observations(yearly_pattern * 5))
    seasonality = next(signal for signal in seasonal if signal.signal_type == "seasonality")
    assert seasonality.direction == "seasonal"
    assert seasonality.metric_value == 1.0
    assert seasonality.evidence["paired_observations"] == 48


def test_recent_spike_and_drop_are_bounded_and_explainable() -> None:
    values = [100] * 60
    values[54] = 250
    values[58] = 20

    signals = detect_demand_signals(_observations(values))
    anomalies = [signal for signal in signals if signal.signal_type == "anomaly"]

    assert [signal.direction for signal in anomalies] == ["spike", "drop"]
    assert all(signal.metric_value >= signal.threshold_value for signal in anomalies)
    assert anomalies[0].evidence["observed_demand"] == 250.0
    assert anomalies[1].evidence["deviation_units"] == -80.0


def test_signal_ids_and_results_are_deterministic() -> None:
    observations = _observations([100] * 50 + [180] + [100] * 9)

    first = detect_demand_signals(observations)
    second = detect_demand_signals(observations)

    assert first == second
    assert all(signal.signal_id.startswith("signal-") for signal in first)
