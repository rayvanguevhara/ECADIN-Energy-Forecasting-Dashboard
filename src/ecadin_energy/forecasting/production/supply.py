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
LOG_SHIFT_GWH = 10.0
STRUCTURAL_BREAK_YEAR = 2021
MIN_NATIONAL_Q95_SAMPLE_SIZE = 10


def _classify_size_bucket(value: float) -> str:
    magnitude = abs(float(value))
    if magnitude < 1000.0:
        return "small"
    if magnitude < 10000.0:
        return "medium"
    return "large"


def _size_bucket_series(values: pd.Series) -> pd.Series:
    return pd.cut(
        values.abs(),
        bins=[-np.inf, 1000.0, 10000.0, np.inf],
        labels=["small", "medium", "large"],
        right=False,
    ).astype("string")


def _drift_horizon_factor(
    horizon: int,
    *,
    anchor_horizon: int = 3,
    history_span: int = 13,
) -> float:
    """Scale horizon uncertainty using Drift slope-estimation variance O(h)."""
    span = max(1, int(history_span))
    h = int(horizon)
    h0 = int(anchor_horizon)
    numerator = h * (1.0 + h / span)
    denominator = h0 * (1.0 + h0 / span)
    return math.sqrt(numerator / denominator)


def _select_regional_bucket_frames(
    drift: pd.DataFrame,
    bucket: str,
) -> dict[int, pd.DataFrame]:
    """Select regime- and bucket-consistent residuals with graded fallbacks."""
    bucket_consistent = drift["origin_size_bucket"].eq(
        drift["target_size_bucket"]
    )
    clean = drift.loc[
        ~drift["crosses_structural_break"] & bucket_consistent
    ]
    same_bucket = drift.loc[bucket_consistent]
    selected: dict[int, pd.DataFrame] = {}
    for horizon in (1, 2, 3):
        candidate = clean.loc[
            clean["horizon"].eq(horizon)
            & clean["target_size_bucket"].eq(bucket)
        ]
        if candidate.empty:
            candidate = same_bucket.loc[
                same_bucket["horizon"].eq(horizon)
                & same_bucket["target_size_bucket"].eq(bucket)
            ]
        if candidate.empty:
            candidate = drift.loc[
                drift["horizon"].eq(horizon)
                & drift["target_size_bucket"].eq(bucket)
            ]
        selected[horizon] = candidate
    return selected


def _calibrate_group(
    frames_by_horizon: dict[int, pd.DataFrame],
    *,
    scope: str,
    bucket: str,
    history_span: int,
) -> list[dict[str, object]]:
    """Compute monotone empirical and Drift-extrapolated quantiles for a group."""
    rows: list[dict[str, object]] = []
    prev_abs_80 = 0.0
    prev_abs_95 = 0.0
    prev_l80 = 0.0
    prev_u80 = 0.0
    prev_l95 = 0.0
    prev_u95 = 0.0

    h3_abs_80 = 0.0
    h3_abs_95 = 0.0
    h3_l80 = 0.0
    h3_u80 = 0.0
    h3_l95 = 0.0
    h3_u95 = 0.0
    h3_count = 0
    h3_q95_suppressed = False

    for horizon in range(1, 7):
        if horizon <= 3:
            frame = frames_by_horizon[horizon].dropna(
                subset=["abs_scaled_error", "log_error"]
            )
            if frame.empty:
                raise ValueError(
                    f"Empty uncertainty residuals: "
                    f"{scope}/{bucket}/h{horizon}"
                )
            abs_vals = frame["abs_scaled_error"]
            log_vals = frame["log_error"]
            count = int(len(frame))

            raw_abs_80 = float(abs_vals.quantile(0.80, interpolation="linear"))
            raw_abs_95 = float(abs_vals.quantile(0.95, interpolation="linear"))
            q80_abs = max(prev_abs_80, raw_abs_80)

            raw_l80 = max(
                0.0, -float(log_vals.quantile(0.10, interpolation="linear"))
            )
            raw_u80 = max(
                0.0, float(log_vals.quantile(0.90, interpolation="linear"))
            )
            q80_l = max(prev_l80, raw_l80)
            q80_u = max(prev_u80, raw_u80)
            coverage_80 = float(
                ((log_vals >= -q80_l) & (log_vals <= q80_u)).mean()
            )

            suppress_q95 = (
                scope == "national" and count < MIN_NATIONAL_Q95_SAMPLE_SIZE
            )
            if suppress_q95:
                q95_abs = np.nan
                q95_l = np.nan
                q95_u = np.nan
                coverage_95 = np.nan
                q95_status = "insufficient_sample_size"
                note = (
                    f"q95 suppressed: insufficient_sample_size "
                    f"(n={count} < {MIN_NATIONAL_Q95_SAMPLE_SIZE})"
                )
            else:
                q95_abs = max(prev_abs_95, raw_abs_95, q80_abs)
                raw_l95 = max(
                    0.0,
                    -float(log_vals.quantile(0.025, interpolation="linear")),
                )
                raw_u95 = max(
                    0.0,
                    float(log_vals.quantile(0.975, interpolation="linear")),
                )
                q95_l = max(prev_l95, raw_l95, q80_l)
                q95_u = max(prev_u95, raw_u95, q80_u)
                coverage_95 = float(
                    ((log_vals >= -q95_l) & (log_vals <= q95_u)).mean()
                )
                prev_abs_95 = q95_abs
                prev_l95 = q95_l
                prev_u95 = q95_u
                if count >= MIN_NATIONAL_Q95_SAMPLE_SIZE:
                    q95_status = "sufficient"
                    note = (
                        "regime-consistent regional calibration"
                        if scope == "regional"
                        else "national empirical calibration"
                    )
                else:
                    q95_status = "limited_sample_stabilized"
                    note = (
                        f"stabilized by monotone floor "
                        f"(n={count} < {MIN_NATIONAL_Q95_SAMPLE_SIZE})"
                    )

            source = (
                "empirical_recursive_drift_regime_consistent"
                if scope == "regional"
                else "empirical_recursive_drift_backtest"
            )
            prev_abs_80 = q80_abs
            prev_l80 = q80_l
            prev_u80 = q80_u

            if horizon == 3:
                h3_abs_80 = q80_abs
                h3_l80 = q80_l
                h3_u80 = q80_u
                h3_count = count
                h3_q95_suppressed = suppress_q95
                if not suppress_q95:
                    h3_abs_95 = float(q95_abs)
                    h3_l95 = float(q95_l)
                    h3_u95 = float(q95_u)
        else:
            factor = _drift_horizon_factor(
                horizon,
                anchor_horizon=3,
                history_span=history_span,
            )
            q80_abs = max(prev_abs_80, h3_abs_80 * factor)
            q80_l = max(prev_l80, h3_l80 * factor)
            q80_u = max(prev_u80, h3_u80 * factor)
            prev_abs_80 = q80_abs
            prev_l80 = q80_l
            prev_u80 = q80_u

            if h3_q95_suppressed:
                q95_abs = np.nan
                q95_l = np.nan
                q95_u = np.nan
                q95_status = "insufficient_sample_size"
                note = (
                    f"q95 suppressed: horizon 3 anchor has "
                    f"insufficient_sample_size "
                    f"(n={h3_count} < {MIN_NATIONAL_Q95_SAMPLE_SIZE})"
                )
            else:
                q95_abs = max(prev_abs_95, h3_abs_95 * factor, q80_abs)
                q95_l = max(prev_l95, h3_l95 * factor, q80_l)
                q95_u = max(prev_u95, h3_u95 * factor, q80_u)
                prev_abs_95 = q95_abs
                prev_l95 = q95_l
                prev_u95 = q95_u
                q95_status = "extrapolated_from_horizon_3"
                note = (
                    f"drift slope-variance scaling from horizon 3 "
                    f"(span={history_span}y)"
                )

            source = "drift_horizon_extrapolation_from_horizon_3"
            count = 0
            coverage_80 = np.nan
            coverage_95 = np.nan

        rows.append(
            {
                "calibration_scope": scope,
                "size_bucket": bucket,
                "horizon": horizon,
                "q80_absolute_scaled_error": q80_abs,
                "q95_absolute_scaled_error": q95_abs,
                "q80_lower_log_error": q80_l,
                "q80_upper_log_error": q80_u,
                "q95_lower_log_error": q95_l,
                "q95_upper_log_error": q95_u,
                "calibration_source": source,
                "calibration_case_count": count,
                "empirical_coverage_80": coverage_80,
                "empirical_coverage_95": coverage_95,
                "scale_floor_gwh": SCALE_FLOOR_GWH,
                "log_shift_gwh": LOG_SHIFT_GWH,
                "q95_status": q95_status,
                "calibration_note": note,
            }
        )
    return rows


def calibrate_uncertainty(
    panel: pd.DataFrame,
    backtest_predictions: pd.DataFrame,
) -> pd.DataFrame:
    """Calibrate asymmetric log-scale supply prediction intervals."""
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
    history_span = (
        max(1, int(eligible["year"].max()) - int(eligible["year"].min()))
        if not eligible.empty
        else 13
    )
    for region_id, group in eligible.groupby("region_id", sort=False):
        lookup[str(region_id)] = (
            group["year"].to_numpy(dtype=int),
            group["training_gwh"].to_numpy(dtype=float),
        )

    origin_values: list[float] = []
    target_last_values: list[float] = []
    for row in drift.itertuples(index=False):
        years, values = lookup[str(row.region_id)]
        valid = np.flatnonzero(years <= int(row.origin_year))
        origin_values.append(
            float(values[int(valid[-1])]) if len(valid) else np.nan
        )
        target_last_values.append(float(values[-1]) if len(values) else np.nan)

    drift["origin_target_gwh"] = origin_values
    drift["target_last_gwh"] = target_last_values
    if drift["origin_target_gwh"].isna().any():
        raise ValueError(
            "Missing origin target during supply uncertainty calibration"
        )

    drift["abs_scaled_error"] = (
        (drift["prediction_gwh"] - drift["actual_gwh"]).abs()
        / drift["origin_target_gwh"].abs().clip(lower=SCALE_FLOOR_GWH)
    )
    drift["log_error"] = np.log(
        (drift["actual_gwh"].clip(lower=0.0) + LOG_SHIFT_GWH)
        / (drift["prediction_gwh"].clip(lower=0.0) + LOG_SHIFT_GWH)
    )
    drift["origin_size_bucket"] = _size_bucket_series(
        drift["origin_target_gwh"]
    )
    drift["target_size_bucket"] = _size_bucket_series(drift["target_last_gwh"])
    drift["crosses_structural_break"] = (
        drift["origin_year"].lt(STRUCTURAL_BREAK_YEAR)
        & drift["forecast_year"].ge(STRUCTURAL_BREAK_YEAR)
    )

    rows: list[dict[str, object]] = []
    for bucket in ("small", "medium", "large"):
        frames = _select_regional_bucket_frames(drift, bucket)
        rows.extend(
            _calibrate_group(
                frames,
                scope="regional",
                bucket=bucket,
                history_span=history_span,
            )
        )

    national = drift.groupby(
        ["origin_year", "forecast_year", "horizon"],
        as_index=False,
    ).agg(
        actual_gwh=("actual_gwh", "sum"),
        prediction_gwh=("prediction_gwh", "sum"),
        origin_target_gwh=("origin_target_gwh", "sum"),
    )
    national["abs_scaled_error"] = (
        (national["prediction_gwh"] - national["actual_gwh"]).abs()
        / national["origin_target_gwh"].abs().clip(lower=SCALE_FLOOR_GWH)
    )
    national["log_error"] = np.log(
        (national["actual_gwh"].clip(lower=0.0) + LOG_SHIFT_GWH)
        / (national["prediction_gwh"].clip(lower=0.0) + LOG_SHIFT_GWH)
    )
    national_frames = {
        horizon: national.loc[national["horizon"].eq(horizon)]
        for horizon in (1, 2, 3)
    }
    rows.extend(
        _calibrate_group(
            national_frames,
            scope="national",
            bucket="all",
            history_span=history_span,
        )
    )
    return pd.DataFrame(rows).sort_values(
        ["calibration_scope", "size_bucket", "horizon"]
    ).reset_index(drop=True)


def build_supply_forecast(
    panel: pd.DataFrame,
    backtest_predictions: pd.DataFrame,
    config: ProductionConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Generate production supply Drift V1 forecasts with calibrated intervals."""
    calibration = calibrate_uncertainty(
        panel,
        backtest_predictions,
    )
    regional_calibration = (
        calibration.loc[calibration["calibration_scope"].eq("regional")]
        .set_index(["size_bucket", "horizon"])
        .to_dict("index")
    )

    model = SupplyDriftV1Model()
    summaries = history_summary(panel)
    value_column = config.supply.output_value_column
    model_version = config.supply.production_model_id
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
        bucket = _classify_size_bucket(last)
        previous = last

        for record in future.to_dict("records"):
            horizon = int(record["horizon"])
            point = float(record["prediction_gwh"])
            raw = float(record["raw_prediction_gwh"])
            calibration_row = regional_calibration[(bucket, horizon)]
            shifted_point = max(0.0, point) + LOG_SHIFT_GWH
            lower_80 = max(
                0.0,
                shifted_point
                * math.exp(-float(calibration_row["q80_lower_log_error"]))
                - LOG_SHIFT_GWH,
            )
            upper_80 = (
                shifted_point
                * math.exp(float(calibration_row["q80_upper_log_error"]))
                - LOG_SHIFT_GWH
            )
            lower_95 = max(
                0.0,
                shifted_point
                * math.exp(-float(calibration_row["q95_lower_log_error"]))
                - LOG_SHIFT_GWH,
            )
            upper_95 = (
                shifted_point
                * math.exp(float(calibration_row["q95_upper_log_error"]))
                - LOG_SHIFT_GWH
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
                    value_column: point,
                    "raw_prediction_gwh": raw,
                    "forecast_lower_80_gwh": lower_80,
                    "forecast_upper_80_gwh": upper_80,
                    "forecast_lower_95_gwh": lower_95,
                    "forecast_upper_95_gwh": upper_95,
                    "forecast_growth_yoy_percent": growth,
                    "cumulative_growth_from_origin_percent": cumulative,
                    "model_id": config.supply.production_model_id,
                    "model_label": config.supply.model_label,
                    "model_version": model_version,
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
        ["modeling_order", "year"]
    ).reset_index(drop=True)
    return forecast, calibration, summaries
