from __future__ import annotations

import pandas as pd

from ecadin_energy.forecasting.evaluation.metrics import (
    build_forecast_record,
)
from ecadin_energy.forecasting.models.base import ForecastModel


def history_at_origin(
    region_frame: pd.DataFrame,
    origin_year: int,
) -> pd.DataFrame:
    history = region_frame.loc[
        region_frame["year"].le(origin_year)
        & region_frame["training_eligible"]
        & region_frame["training_gwh"].notna(),
        ["year", "training_gwh"],
    ].copy()
    return (
        history.rename(columns={"training_gwh": "target_gwh"})
        .sort_values("year")
        .reset_index(drop=True)
    )


def run_one_step_for_model(
    region_frame: pd.DataFrame,
    *,
    model: ForecastModel,
    domain: str,
    model_version: str,
    reference_baseline: str,
    target_years: tuple[int, ...],
) -> list[dict[str, object]]:
    region_id = str(region_frame.iloc[0]["region_id"])
    region_name = str(region_frame.iloc[0]["region_name"])
    rows: list[dict[str, object]] = []

    for target_year in target_years:
        validation = region_frame.loc[
            region_frame["year"].eq(target_year)
            & region_frame["validation_eligible"]
            & region_frame["actual_gwh"].notna()
        ]
        if validation.empty:
            continue
        origin_year = int(target_year) - 1
        history = history_at_origin(region_frame, origin_year)
        actual = float(validation.iloc[0]["actual_gwh"])
        raw_prediction = model.predict_next(history, int(target_year))
        record = build_forecast_record(
            domain=domain,
            model_version=model_version,
            protocol="rolling_one_step",
            model=model.model_id,
            reference_baseline=reference_baseline,
            region_id=region_id,
            region_name=region_name,
            origin_year=origin_year,
            forecast_year=int(target_year),
            horizon=1,
            history_for_scale=history,
            actual=actual,
            raw_prediction=raw_prediction,
        )
        rows.append(record.as_dict())
    return rows
