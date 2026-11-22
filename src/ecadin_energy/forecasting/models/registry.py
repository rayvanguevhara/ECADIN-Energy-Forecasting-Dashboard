from __future__ import annotations

from collections.abc import Iterable

from ecadin_energy.forecasting.configuration import SupplyModelParams
from ecadin_energy.forecasting.models.baselines import (
    AverageGrowth3Model,
    MovingAverage3Model,
    NaiveLag1Model,
)
from ecadin_energy.forecasting.models.base import (
    ForecastModel,
    PanelForecastModel,
)
from ecadin_energy.forecasting.models.drift import DriftModel
from ecadin_energy.forecasting.models.drift_v1 import SupplyDriftV1Model
from ecadin_energy.forecasting.models.national_reconciled import (
    NationalReconciledSupplyModel,
)


MODEL_REGISTRY: dict[str, type[ForecastModel]] = {
    "naive_lag1": NaiveLag1Model,
    "drift": DriftModel,
    "moving_average_3": MovingAverage3Model,
    "average_growth_3": AverageGrowth3Model,
    "supply_production_drift_v1": SupplyDriftV1Model,
}

PANEL_MODEL_REGISTRY: dict[str, type[NationalReconciledSupplyModel]] = {
    "national_reconciled_supply": NationalReconciledSupplyModel,
    "supply_production_national_reconciled_v2": NationalReconciledSupplyModel,
}


def is_panel_model(model_id: str) -> bool:
    return model_id in PANEL_MODEL_REGISTRY


def create_model(model_id: str) -> ForecastModel:
    try:
        model_class = MODEL_REGISTRY[model_id]
    except KeyError as exc:
        raise KeyError(f"Unknown forecasting model: {model_id}") from exc
    return model_class()


def create_panel_model(
    model_id: str,
    *,
    params: SupplyModelParams | None,
    model_label: str | None = None,
) -> PanelForecastModel:
    try:
        model_class = PANEL_MODEL_REGISTRY[model_id]
    except KeyError as exc:
        raise KeyError(
            f"Unknown panel forecasting model: {model_id}"
        ) from exc
    if params is None:
        raise ValueError(
            f"SupplyModelParams from config is required for {model_id}"
        )
    return model_class.from_params(
        params,
        model_id="national_reconciled_supply"
        if model_id == "national_reconciled_supply"
        else model_id,
        model_label=model_label,
    )


def create_models(model_ids: Iterable[str]) -> list[ForecastModel]:
    return [create_model(model_id) for model_id in model_ids]
