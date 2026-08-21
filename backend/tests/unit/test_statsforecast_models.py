"""Focused tests for the StatsForecast model adapter registry."""

import math

from app.infrastructure.forecasting import build_candidate_models


def test_regular_candidate_registry_produces_monthly_forecasts() -> None:
    models = build_candidate_models(intermittent=False)
    history = tuple(float(100 + month + month % 12) for month in range(36))

    predictions = {model.name: model.predict(history, 3, 90) for model in models}

    assert tuple(predictions) == (
        "Naive",
        "SeasonalNaive",
        "RandomWalkWithDrift",
        "AutoETS",
        "AutoTheta",
    )
    assert all(len(prediction.mean) == 3 for prediction in predictions.values())
    assert all(
        math.isfinite(value) for prediction in predictions.values() for value in prediction.mean
    )


def test_intermittent_registry_includes_croston_without_fake_native_intervals() -> None:
    models = build_candidate_models(intermittent=True)
    croston = next(model for model in models if model.name == "CrostonOptimized")

    prediction = croston.predict(tuple(float(index % 5 == 0) for index in range(36)), 3, 90)

    assert prediction.lower is None
    assert prediction.upper is None
    assert len(prediction.mean) == 3
