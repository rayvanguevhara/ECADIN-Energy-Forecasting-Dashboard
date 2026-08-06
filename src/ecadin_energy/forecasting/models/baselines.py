from __future__ import annotations

import pandas as pd


class NaiveLag1Model:
    model_id = "naive_lag1"
    model_label = "Naive Lag-1"

    def predict_next(
        self,
        history: pd.DataFrame,
        target_year: int,
    ) -> float:
        if history.empty:
            return float("nan")
        return float(history.iloc[-1]["target_gwh"])


class MovingAverage3Model:
    model_id = "moving_average_3"
    model_label = "Moving Average 3"

    def predict_next(
        self,
        history: pd.DataFrame,
        target_year: int,
    ) -> float:
        if history.empty:
            return float("nan")
        return float(history.tail(3)["target_gwh"].mean())


class AverageGrowth3Model:
    model_id = "average_growth_3"
    model_label = "Average Growth 3"

    def predict_next(
        self,
        history: pd.DataFrame,
        target_year: int,
    ) -> float:
        if history.empty:
            return float("nan")
        positive = history.loc[history["target_gwh"] > 0].tail(4)
        if len(positive) < 2:
            return float(history.iloc[-1]["target_gwh"])

        first = positive.iloc[0]
        last = positive.iloc[-1]
        span = int(last["year"] - first["year"])
        if span <= 0 or float(first["target_gwh"]) <= 0:
            return float(history.iloc[-1]["target_gwh"])

        annual_growth = (
            float(last["target_gwh"]) / float(first["target_gwh"])
        ) ** (1.0 / span) - 1.0
        steps = int(target_year) - int(last["year"])
        return float(
            float(last["target_gwh"])
            * ((1.0 + annual_growth) ** steps)
        )
