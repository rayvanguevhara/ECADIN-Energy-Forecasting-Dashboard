from __future__ import annotations

import math

import numpy as np
import pandas as pd

from ecadin_energy.forecasting.configuration import ProductionConfig
from ecadin_energy.forecasting.models.drift_v1 import SupplyDriftV1Model
from ecadin_energy.forecasting.production.common import (
    history_summary,
    training_history,
)
from ecadin_energy.forecasting.strategies.recursive import (
    recursive_forecast_without_actuals,
)


SUPPLY_MODEL_VERSION = "supply_production_drift_v1"
SCALE_FLOOR_GWH = 100.0


def calibrate_uncertainty(
    panel: pd.DataFrame,
    backtest_predictions: pd.DataFrame,
) -> pd.DataFrame:
    drift = backtest_predictions.loc[
        backtest_predictions["protocol"].eq("recursive_multi_step")
        & backtest_predictions["model"].eq("drift")
        & backtest_predictions["horizon"].isin([1, 2, 3])
    ].copy()

    lookup: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    eligible = panel.loc[
        panel["training_eligible"] & panel["training_gwh"].notna(),
        ["region_id", "year", "training_gwh"],
    ].sort_values(["region_id", "year"])
    for region_id, group in eligible.groupby("region_id", sort=False):
        lookup[str(region_id)] = (
            group["year"].to_numpy(dtype=int),
            group["training_gwh"].to_numpy(dtype=float),
        )

    origin_values: list[float] = []
    for row in drift.itertuples(index=False):
        years, values = lookup[str(row.region_id)]
        valid = np.flatnonzero(years <= int(row.origin_year))
        origin_values.append(
            float(values[int(valid[-1])]) if len(valid) else np.nan
        )
    drift["origin_target_gwh"] = origin_values
    if drift["origin_target_gwh"].isna().any():
        raise ValueError(
            "Missing origin target during supply uncertainty calibration"
        )

    drift["abs_scaled_error"] = (
        (
            drift["prediction_gwh"] - drift["actual_gwh"]
        ).abs()
        / drift["origin_target_gwh"].abs().clip(
            lower=SCALE_FLOOR_GWH
        )
    )
    drift["size_bucket"] = pd.cut(
        drift["origin_target_gwh"].abs(),
        bins=[-np.inf, 1000.0, 10000.0, np.inf],
        labels=["small", "medium", "large"],
        right=False,
    ).astype("string")

    def calibrate_group(
        values_by_horizon: dict[int, pd.Series],
        scope: str,
        bucket: str,
    ) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        previous_80 = 0.0
        previous_95 = 0.0
        horizon_3_80: float | None = None
        horizon_3_95: float | None = None

        for horizon in range(1, 7):
            if horizon <= 3:
                values = values_by_horizon[horizon].dropna()
                if values.empty:
                    raise ValueError(
                        f"Empty uncertainty residuals: "
                        f"{scope}/{bucket}/h{horizon}"
                    )
                raw_80 = float(
                    values.quantile(0.80, interpolation="linear")
                )
                raw_95 = float(
                    values.quantile(0.95, interpolation="linear")
                )
                quantile_80 = max(previous_80, raw_80)
                quantile_95 = max(
                    previous_95,
                    raw_95,
                    quantile_80,
                )
                source = "empirical_recursive_drift_backtest"
                count = int(len(values))
                coverage_80 = float((values <= quantile_80).mean())
                coverage_95 = float((values <= quantile_95).mean())
            else:
                factor = math.sqrt(horizon / 3.0)
                quantile_80 = max(
                    previous_80,
                    float(horizon_3_80) * factor,
                )
                quantile_95 = max(
                    previous_95,
                    float(horizon_3_95) * factor,
                    quantile_80,
                )
                source = "sqrt_extrapolation_from_horizon_3"
                count = 0
                coverage_80 = np.nan
                coverage_95 = np.nan

            rows.append(
                {
                    "calibration_scope": scope,
                    "size_bucket": bucket,
                    "horizon": horizon,
                    "q80_absolute_scaled_error": quantile_80,
                    "q95_absolute_scaled_error": quantile_95,
                    "calibration_source": source,
                    "calibration_case_count": count,
                    "empirical_coverage_80": coverage_80,
                    "empirical_coverage_95": coverage_95,
                    "scale_floor_gwh": SCALE_FLOOR_GWH,
                }
            )
            previous_80 = quantile_80
            previous_95 = quantile_95
            if horizon == 3:
                horizon_3_80 = quantile_80
                horizon_3_95 = quantile_95
        return rows

    rows: list[dict[str, object]] = []
    for bucket in ("small", "medium", "large"):
        values = {
            horizon: drift.loc[
                drift["horizon"].eq(horizon)
                & drift["size_bucket"].eq(bucket),
                "abs_scaled_error",
            ]
            for horizon in (1, 2, 3)
        }
        rows.extend(calibrate_group(values, "regional", bucket))

    national = drift.groupby(
        ["origin_year", "forecast_year", "horizon"],
        as_index=False,
    ).agg(
        actual_gwh=("actual_gwh", "sum"),
        prediction_gwh=("prediction_gwh", "sum"),
        origin_target_gwh=("origin_target_gwh", "sum"),
    )
    national["abs_scaled_error"] = (
        (
            national["prediction_gwh"] - national["actual_gwh"]
        ).abs()
        / national["origin_target_gwh"].abs().clip(
            lower=SCALE_FLOOR_GWH
        )
    )
    national_values = {
        horizon: national.loc[
            national["horizon"].eq(horizon),
            "abs_scaled_error",
        ]
        for horizon in (1, 2, 3)
    }
    rows.extend(
        calibrate_group(national_values, "national", "all")
    )
    return pd.DataFrame(rows).sort_values(
        ["calibration_scope", "size_bucket", "horizon"]
    ).reset_index(drop=True)


def build_supply_forecast(
    panel: pd.DataFrame,
    backtest_predictions: pd.DataFrame,
    config: ProductionConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    calibration = calibrate_uncertainty(
        panel,
        backtest_predictions,
    )
    regional_calibration = calibration.loc[
        calibration["calibration_scope"].eq("regional")
    ].set_index(["size_bucket", "horizon"]).to_dict("index")

    model = SupplyDriftV1Model()
    summaries = history_summary(panel)
    rows: list[dict[str, object]] = []

    for _, group in panel.groupby("region_id", sort=False):
        history = training_history(group)
        future = recursive_forecast_without_actuals(
            history,
            model=model,
            forecast_years=config.forecast_years,
        )
        summary = summaries.loc[
            summaries["region_id"].eq(group.iloc[0]["region_id"])
        ].iloc[0]
        last = float(summary["history_last_gwh"])
        scale = max(abs(last), SCALE_FLOOR_GWH)
        bucket = (
            "small"
            if abs(last) < 1000
            else "medium"
            if abs(last) < 10000
            else "large"
        )
        previous = last

        for record in future.to_dict("records"):
            horizon = int(record["horizon"])
            point = float(record["prediction_gwh"])
            raw = float(record["raw_prediction_gwh"])
            calibration_row = regional_calibration[(bucket, horizon)]
            width_80 = (
                float(
                    calibration_row[
                        "q80_absolute_scaled_error"
                    ]
                )
                * scale
            )
            width_95 = (
                float(
                    calibration_row[
                        "q95_absolute_scaled_error"
                    ]
                )
                * scale
            )
            growth = (
                np.nan
                if previous == 0
                else 100.0 * (point / previous - 1.0)
            )
            cumulative = (
                np.nan
                if last == 0
                else 100.0 * (point / last - 1.0)
            )
            rows.append(
                {
                    "region_id": str(group.iloc[0]["region_id"]),
                    "region_name": str(group.iloc[0]["region_name"]),
                    "modeling_order": int(
                        group.iloc[0]["modeling_order"]
                    ),
                    "year": int(record["year"]),
                    "forecast_gwh": point,
                    "raw_prediction_gwh": raw,
                    "forecast_lower_80_gwh": max(
                        0.0,
                        point - width_80,
                    ),
                    "forecast_upper_80_gwh": point + width_80,
                    "forecast_lower_95_gwh": max(
                        0.0,
                        point - width_95,
                    ),
                    "forecast_upper_95_gwh": point + width_95,
                    "forecast_growth_yoy_percent": growth,
                    "cumulative_growth_from_origin_percent": cumulative,
                    "model_id": config.supply.production_model_id,
                    "model_label": config.supply.model_label,
                    "model_version": SUPPLY_MODEL_VERSION,
                    "forecast_type": "recursive_drift_forecast",
                    "origin_year": int(record["origin_year"]),
                    "horizon": horizon,
                    "was_clipped_nonnegative": bool(
                        record["was_clipped_nonnegative"]
                    ),
                    "history_first_year": int(
                        summary["history_first_year"]
                    ),
                    "history_last_year": int(
                        summary["history_last_year"]
                    ),
                    "history_first_gwh": float(
                        summary["history_first_gwh"]
                    ),
                    "history_last_gwh": last,
                    "drift_slope_gwh_per_year": float(
                        summary["drift_slope_gwh_per_year"]
                    ),
                    "uncertainty_size_bucket": bucket,
                    "uncertainty_scale_gwh": scale,
                    "uncertainty_calibration_source": str(
                        calibration_row["calibration_source"]
                    ),
                }
            )
            previous = point

    forecast = pd.DataFrame(rows).sort_values(
        ["year", "modeling_order"]
    ).reset_index(drop=True)
    return forecast, calibration, summaries
