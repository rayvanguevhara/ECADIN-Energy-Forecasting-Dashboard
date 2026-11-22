from __future__ import annotations

from typing import Protocol, runtime_checkable

import pandas as pd


class ForecastModel(Protocol):
    model_id: str
    model_label: str

    def predict_next(
        self,
        history: pd.DataFrame,
        target_year: int,
    ) -> float:
        """Return an unconstrained next prediction."""


@runtime_checkable
class PanelForecastModel(Protocol):
    model_id: str
    model_label: str

    def forecast_panel(
        self,
        panel_history: pd.DataFrame,
        origin_year: int,
        forecast_years: tuple[int, ...],
        region_ids: tuple[str, ...],
    ) -> dict[tuple[str, int], float]:
        """Return region-year predictions constrained across a panel."""
