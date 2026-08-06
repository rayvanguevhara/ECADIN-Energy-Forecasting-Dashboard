from __future__ import annotations

import pandas as pd


class DriftModel:
    """Linear drift from the first to the latest available observation."""

    model_id = "drift"
    model_label = "Drift"

    def predict_next(
        self,
        history: pd.DataFrame,
        target_year: int,
    ) -> float:
        if history.empty:
            return float("nan")
        if len(history) < 2:
            return float(history.iloc[-1]["target_gwh"])

        first = history.iloc[0]
        last = history.iloc[-1]
        span = int(last["year"] - first["year"])
        if span <= 0:
            return float(last["target_gwh"])

        slope = (
            float(last["target_gwh"]) - float(first["target_gwh"])
        ) / span
        steps = int(target_year) - int(last["year"])
        return float(last["target_gwh"] + slope * steps)


def drift_slope(history: pd.DataFrame) -> float:
    if len(history) < 2:
        return 0.0
    first = history.iloc[0]
    last = history.iloc[-1]
    span = int(last["year"] - first["year"])
    if span <= 0:
        return 0.0
    return (
        float(last["target_gwh"]) - float(first["target_gwh"])
    ) / span
