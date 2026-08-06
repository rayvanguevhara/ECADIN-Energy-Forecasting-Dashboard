from __future__ import annotations

from collections.abc import Iterable

from ecadin_energy.forecasting.models.baselines import (
    AverageGrowth3Model,
    MovingAverage3Model,
    NaiveLag1Model,
)
from ecadin_energy.forecasting.models.base import ForecastModel
from ecadin_energy.forecasting.models.drift import DriftModel
from ecadin_energy.forecasting.models.drift_v1 import SupplyDriftV1Model


MODEL_REGISTRY: dict[str, type[ForecastModel]] = {
    "naive_lag1": NaiveLag1Model,
    "drift": DriftModel,
    "moving_average_3": MovingAverage3Model,
    "average_growth_3": AverageGrowth3Model,
    "supply_production_drift_v1": SupplyDriftV1Model,
}


def create_model(model_id: str) -> ForecastModel:
    try:
        model_class = MODEL_REGISTRY[model_id]
    except KeyError as exc:
        raise KeyError(f"Unknown forecasting model: {model_id}") from exc
    return model_class()


def create_models(model_ids: Iterable[str]) -> list[ForecastModel]:
    return [create_model(model_id) for model_id in model_ids]
