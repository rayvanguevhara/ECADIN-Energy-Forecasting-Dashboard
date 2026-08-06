from __future__ import annotations

import math

import numpy as np
import pandas as pd

from ecadin_energy.forecasting.contracts import ForecastRecord


def clip_nonnegative(value: float) -> tuple[float, bool]:
    if not np.isfinite(value):
        return float("nan"), False
    clipped = bool(value < 0)
    return float(max(0.0, value)), clipped


def smape(actual: float, prediction: float) -> float:
    denominator = abs(actual) + abs(prediction)
    if denominator == 0:
        return 0.0
    return 200.0 * abs(prediction - actual) / denominator


def mase_scale(history: pd.DataFrame) -> float:
    values = history["target_gwh"].to_numpy(dtype=float)
    if len(values) < 2:
        return float("nan")
    scale = float(np.mean(np.abs(np.diff(values))))
    return scale if np.isfinite(scale) and scale > 0 else float("nan")


def build_forecast_record(
    *,
    domain: str,
    model_version: str,
    protocol: str,
    model: str,
    reference_baseline: str,
    region_id: str,
    region_name: str,
    origin_year: int,
    forecast_year: int,
    horizon: int,
    history_for_scale: pd.DataFrame,
    actual: float,
    raw_prediction: float,
) -> ForecastRecord:
    prediction, clipped = clip_nonnegative(raw_prediction)
    error = prediction - actual
    absolute_error = abs(error)
    scale = mase_scale(history_for_scale)
    ape = (
        None
        if actual == 0
        else 100.0 * absolute_error / abs(actual)
    )
    mase_value = (
        None
        if not np.isfinite(scale)
        else absolute_error / scale
    )
    first_year = (
        int(history_for_scale["year"].min())
        if not history_for_scale.empty
        else None
    )
    last_year = (
        int(history_for_scale["year"].max())
        if not history_for_scale.empty
        else None
    )
    return ForecastRecord(
        domain=domain,
        model_version=model_version,
        protocol=protocol,
        model=model,
        reference_baseline=reference_baseline,
        region_id=region_id,
        region_name=region_name,
        origin_year=int(origin_year),
        forecast_year=int(forecast_year),
        horizon=int(horizon),
        actual_gwh=float(actual),
        prediction_raw_gwh=float(raw_prediction),
        prediction_gwh=float(prediction),
        error_gwh=float(error),
        absolute_error_gwh=float(absolute_error),
        squared_error_gwh2=float(error**2),
        ape_percent=(
            float(ape) if ape is not None and math.isfinite(ape) else None
        ),
        smape_percent=float(smape(actual, prediction)),
        mase_scale_gwh=(
            float(scale) if np.isfinite(scale) else None
        ),
        mase=(
            float(mase_value)
            if mase_value is not None and math.isfinite(mase_value)
            else None
        ),
        training_observation_count=int(len(history_for_scale)),
        training_first_year=first_year,
        training_last_year=last_year,
        was_clipped_nonnegative=clipped,
    )
