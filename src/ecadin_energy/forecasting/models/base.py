from __future__ import annotations

from typing import Protocol

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
