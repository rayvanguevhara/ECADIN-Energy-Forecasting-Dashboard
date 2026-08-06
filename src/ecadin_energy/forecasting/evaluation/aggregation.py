from __future__ import annotations

import numpy as np
import pandas as pd


def metric_record(group: pd.DataFrame) -> dict[str, object]:
    error = group["error_gwh"].to_numpy(dtype=float)
    actual = group["actual_gwh"].to_numpy(dtype=float)
    prediction = group["prediction_gwh"].to_numpy(dtype=float)
    by_region = group.groupby("region_id", sort=False)
    region_smape = by_region["smape_percent"].mean()
    region_mase = by_region["mase"].mean()
    aggregate_actual = float(np.sum(actual))
    aggregate_error = float(np.sum(error))
    return {
        "prediction_count": int(len(group)),
        "region_count": int(group["region_id"].nunique()),
        "forecast_year_count": int(
            group["forecast_year"].nunique()
        ),
        "micro_mae_gwh": float(np.mean(np.abs(error))),
        "micro_rmse_gwh": float(np.sqrt(np.mean(error**2))),
        "micro_smape_percent": float(
            group["smape_percent"].mean()
        ),
        "micro_mape_percent": float(group["ape_percent"].mean()),
        "macro_smape_percent": float(region_smape.mean()),
        "macro_mase": float(region_mase.mean()),
        "mean_bias_gwh": float(np.mean(error)),
        "aggregate_bias_gwh": aggregate_error,
        "aggregate_bias_percent": (
            np.nan
            if aggregate_actual == 0
            else 100.0 * aggregate_error / aggregate_actual
        ),
        "actual_total_gwh": aggregate_actual,
        "prediction_total_gwh": float(np.sum(prediction)),
        "clipped_prediction_count": int(
            group["was_clipped_nonnegative"].sum()
        ),
    }


def metrics_summary(predictions: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    keys = ["domain", "protocol", "model"]
    for key, group in predictions.groupby(keys, sort=True):
        rows.append({**dict(zip(keys, key)), **metric_record(group)})
    return pd.DataFrame(rows).sort_values(
        ["domain", "protocol", "macro_smape_percent", "model"]
    ).reset_index(drop=True)


def metrics_by_fold(predictions: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    keys = [
        "domain",
        "protocol",
        "model",
        "origin_year",
        "forecast_year",
    ]
    for key, group in predictions.groupby(keys, sort=True):
        rows.append({**dict(zip(keys, key)), **metric_record(group)})
    return pd.DataFrame(rows)


def metrics_by_horizon(predictions: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    keys = ["domain", "protocol", "model", "horizon"]
    for key, group in predictions.groupby(keys, sort=True):
        rows.append({**dict(zip(keys, key)), **metric_record(group)})
    return pd.DataFrame(rows)


def metrics_by_region(predictions: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    keys = ["domain", "protocol", "model", "region_id", "region_name"]
    for key, group in predictions.groupby(keys, sort=True):
        error = group["error_gwh"].to_numpy(dtype=float)
        actual_total = float(group["actual_gwh"].sum())
        rows.append(
            {
                **dict(zip(keys, key)),
                "prediction_count": int(len(group)),
                "mae_gwh": float(np.mean(np.abs(error))),
                "rmse_gwh": float(np.sqrt(np.mean(error**2))),
                "smape_percent": float(
                    group["smape_percent"].mean()
                ),
                "mase": float(group["mase"].mean()),
                "mean_bias_gwh": float(np.mean(error)),
                "aggregate_bias_percent": (
                    np.nan
                    if actual_total == 0
                    else 100.0
                    * float(group["error_gwh"].sum())
                    / actual_total
                ),
            }
        )
    return pd.DataFrame(rows)
