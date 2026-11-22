from __future__ import annotations

import pandas as pd

from ecadin_energy.forecasting.evaluation.metrics import (
    build_forecast_record,
    clip_nonnegative,
)
from ecadin_energy.forecasting.models.base import ForecastModel
from ecadin_energy.forecasting.strategies.one_step import (
    history_at_origin,
)


def run_recursive_for_model(
    region_frame: pd.DataFrame,
    *,
    model: ForecastModel,
    domain: str,
    model_version: str,
    reference_baseline: str,
    origins: tuple[int, ...],
    max_horizon: int,
) -> list[dict[str, object]]:
    region_id = str(region_frame.iloc[0]["region_id"])
    region_name = str(region_frame.iloc[0]["region_name"])
    actual_lookup = region_frame.set_index("year")["actual_gwh"].to_dict()
    eligible_lookup = region_frame.set_index("year")[
        "validation_eligible"
    ].to_dict()
    rows: list[dict[str, object]] = []

    for origin_year in origins:
        base_history = history_at_origin(region_frame, origin_year)
        recursive_history = base_history.copy()
        scale_history = base_history.copy()

        for horizon in range(1, max_horizon + 1):
            target_year = int(origin_year) + horizon
            raw_prediction = model.predict_next(
                recursive_history,
                target_year,
            )
            prediction, _ = clip_nonnegative(raw_prediction)

            is_eligible = bool(eligible_lookup.get(target_year, False))
            actual = actual_lookup.get(target_year)
            if is_eligible and pd.notna(actual):
                record = build_forecast_record(
                    domain=domain,
                    model_version=model_version,
                    protocol="recursive_multi_step",
                    model=model.model_id,
                    reference_baseline=reference_baseline,
                    region_id=region_id,
                    region_name=region_name,
                    origin_year=int(origin_year),
                    forecast_year=target_year,
                    horizon=horizon,
                    history_for_scale=scale_history,
                    actual=float(actual),
                    raw_prediction=raw_prediction,
                )
                rows.append(record.as_dict())

            if pd.notna(prediction):
                recursive_history = pd.concat(
                    [
                        recursive_history,
                        pd.DataFrame(
                            {
                                "year": [target_year],
                                "target_gwh": [prediction],
                            }
                        ),
                    ],
                    ignore_index=True,
                )
    return rows


def recursive_forecast_without_actuals(
    history: pd.DataFrame,
    *,
    model: ForecastModel,
    forecast_years: tuple[int, ...],
) -> pd.DataFrame:
    if history.empty:
        raise ValueError("Cannot forecast from empty history")
    recursive_history = history[["year", "target_gwh"]].copy()
    rows: list[dict[str, object]] = []
    origin_year = int(recursive_history["year"].max())

    for horizon, target_year in enumerate(forecast_years, start=1):
        raw_prediction = model.predict_next(
            recursive_history,
            int(target_year),
        )
        prediction, clipped = clip_nonnegative(raw_prediction)
        rows.append(
            {
                "origin_year": origin_year,
                "year": int(target_year),
                "horizon": horizon,
                "raw_prediction_gwh": float(raw_prediction),
                "prediction_gwh": float(prediction),
                "was_clipped_nonnegative": bool(clipped),
            }
        )
        recursive_history = pd.concat(
            [
                recursive_history,
                pd.DataFrame(
                    {
                        "year": [int(target_year)],
                        "target_gwh": [prediction],
                    }
                ),
            ],
            ignore_index=True,
        )
    return pd.DataFrame(rows)
