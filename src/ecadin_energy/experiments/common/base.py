from __future__ import annotations

from typing import Protocol, runtime_checkable

import pandas as pd

from ecadin_energy.forecasting.evaluation.metrics import clip_nonnegative
from ecadin_energy.forecasting.models.base import ForecastModel
from ecadin_energy.forecasting.models.registry import create_model


@runtime_checkable
class SeriesExperimentModel(Protocol):
    model_id: str
    model_label: str
    family: str
    is_baseline: bool

    def forecast_horizons(
        self,
        history: pd.DataFrame,
        origin_year: int,
        forecast_years: tuple[int, ...],
    ) -> dict[int, float]:
        """Return unclipped predictions keyed by target forecast year."""


@runtime_checkable
class PanelExperimentModel(Protocol):
    model_id: str
    model_label: str
    family: str
    is_baseline: bool

    def forecast_panel(
        self,
        panel_history: pd.DataFrame,
        origin_year: int,
        forecast_years: tuple[int, ...],
        region_ids: tuple[str, ...],
    ) -> dict[tuple[str, int], float]:
        """Return unclipped predictions keyed by (region_id, target_year)."""


class BaselineRecursiveAdapter:
    """Adapter wrapping production ForecastModel baselines for multi-step recursion."""

    def __init__(self, model_id: str) -> None:
        self._model: ForecastModel = create_model(model_id)
        self.model_id = self._model.model_id
        self.model_label = self._model.model_label
        self.family = "baseline"
        self.is_baseline = True

    def forecast_horizons(
        self,
        history: pd.DataFrame,
        origin_year: int,
        forecast_years: tuple[int, ...],
    ) -> dict[int, float]:
        ordered = (
            history.loc[history["year"] <= int(origin_year), ["year", "target_gwh"]]
            .dropna(subset=["year", "target_gwh"])
            .sort_values("year")
            .reset_index(drop=True)
        )
        if ordered.empty:
            return {int(year): float("nan") for year in forecast_years}

        recursive_history = ordered.copy()
        predictions: dict[int, float] = {}
        for target_year in forecast_years:
            target = int(target_year)
            raw_prediction = float(self._model.predict_next(recursive_history, target))
            clipped, _ = clip_nonnegative(raw_prediction)
            predictions[target] = raw_prediction
            if pd.notna(clipped):
                recursive_history = pd.concat(
                    [
                        recursive_history,
                        pd.DataFrame(
                            {
                                "year": [target],
                                "target_gwh": [float(clipped)],
                            }
                        ),
                    ],
                    ignore_index=True,
                )
        return predictions
