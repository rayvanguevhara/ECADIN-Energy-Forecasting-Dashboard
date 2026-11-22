from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd

from ecadin_energy.experiments.common.base import (
    PanelExperimentModel,
    SeriesExperimentModel,
)
from ecadin_energy.forecasting.configuration import ProductionConfig
from ecadin_energy.forecasting.evaluation.aggregation import metric_record
from ecadin_energy.forecasting.evaluation.challenger import (
    win_rate_vs_reference,
)
from ecadin_energy.forecasting.evaluation.metrics import (
    build_forecast_record,
    clip_nonnegative,
)
from ecadin_energy.forecasting.production.common import training_history
from ecadin_energy.forecasting.strategies.one_step import history_at_origin


EXPERIMENT_MODEL_VERSION = "phase2_experiments_v1"

EXTENDED_ORIGIN_HORIZONS: dict[int, tuple[int, ...]] = {
    2018: (1, 2, 3, 4, 5, 6),
    2019: (1, 2, 3, 4, 5),
    2020: (1, 2, 3, 4),
}

SUPPLY_KEY_PROVINCES: tuple[str, ...] = (
    "LA",
    "BE",
    "KT",
    "SG",
    "KS",
    "SS",
    "JI",
    "JB",
    "JT",
    "YO",
)

DEMAND_KEY_PROVINCES: tuple[str, ...] = (
    "KR",
    "BT",
    "JK",
    "JI",
    "JB",
    "KU",
)


@dataclass(frozen=True)
class ModelMetadata:
    model_id: str
    model_label: str
    family: str
    is_baseline: bool


def collect_model_metadata(
    series_models: tuple[SeriesExperimentModel, ...],
    panel_models: tuple[PanelExperimentModel, ...],
) -> dict[str, ModelMetadata]:
    meta: dict[str, ModelMetadata] = {}
    for model in (*series_models, *panel_models):
        meta[model.model_id] = ModelMetadata(
            model_id=model.model_id,
            model_label=model.model_label,
            family=model.family,
            is_baseline=model.is_baseline,
        )
    return meta


def run_domain_backtests(
    panel: pd.DataFrame,
    config: ProductionConfig,
    *,
    domain: str,
    series_models: tuple[SeriesExperimentModel, ...],
    panel_models: tuple[PanelExperimentModel, ...],
) -> pd.DataFrame:
    """Evaluate all series and panel models across the 3 backtest protocols."""
    region_frames: dict[str, pd.DataFrame] = {
        str(rid): group.sort_values("year").reset_index(drop=True)
        for rid, group in panel.groupby("region_id", sort=False)
    }
    region_ids = tuple(region_frames.keys())
    region_names = {
        rid: str(frame.iloc[0]["region_name"])
        for rid, frame in region_frames.items()
    }
    actual_lookups = {
        rid: frame.set_index("year")["actual_gwh"].to_dict()
        for rid, frame in region_frames.items()
    }
    eligible_lookups = {
        rid: frame.set_index("year")["validation_eligible"].to_dict()
        for rid, frame in region_frames.items()
    }

    rows: list[dict[str, object]] = []

    def _append_record(
        *,
        protocol: str,
        model_id: str,
        region_id: str,
        origin_year: int,
        target_year: int,
        horizon: int,
        scale_history: pd.DataFrame,
        raw_prediction: float,
    ) -> None:
        is_eligible = bool(eligible_lookups[region_id].get(target_year, False))
        actual = actual_lookups[region_id].get(target_year)
        if not is_eligible or pd.isna(actual):
            return
        record = build_forecast_record(
            domain=domain,
            model_version=EXPERIMENT_MODEL_VERSION,
            protocol=protocol,
            model=model_id,
            reference_baseline=config.reference_baseline,
            region_id=region_id,
            region_name=region_names[region_id],
            origin_year=int(origin_year),
            forecast_year=int(target_year),
            horizon=int(horizon),
            history_for_scale=scale_history,
            actual=float(actual),
            raw_prediction=float(raw_prediction),
        )
        rows.append(record.as_dict())

    # 1. rolling_one_step (target_years 2019..2024)
    for target_year in config.one_step_target_years:
        target = int(target_year)
        origin = target - 1
        panel_hist = panel.loc[
            panel["year"].le(origin)
            & panel["training_eligible"]
            & panel["training_gwh"].notna()
        ].copy()
        for p_model in panel_models:
            pred_map = p_model.forecast_panel(
                panel_hist,
                origin,
                (target,),
                region_ids,
            )
            for region_id in region_ids:
                scale_hist = history_at_origin(region_frames[region_id], origin)
                _append_record(
                    protocol="rolling_one_step",
                    model_id=p_model.model_id,
                    region_id=region_id,
                    origin_year=origin,
                    target_year=target,
                    horizon=1,
                    scale_history=scale_hist,
                    raw_prediction=pred_map[(region_id, target)],
                )
        for region_id in region_ids:
            scale_hist = history_at_origin(region_frames[region_id], origin)
            for s_model in series_models:
                pred_map = s_model.forecast_horizons(scale_hist, origin, (target,))
                _append_record(
                    protocol="rolling_one_step",
                    model_id=s_model.model_id,
                    region_id=region_id,
                    origin_year=origin,
                    target_year=target,
                    horizon=1,
                    scale_history=scale_hist,
                    raw_prediction=pred_map[target],
                )

    # 2. recursive_multi_step_h3 (origins 2018..2021, h=1..3)
    h3_horizons = tuple(range(1, config.recursive_max_horizon + 1))
    for origin_year in config.recursive_origins:
        origin = int(origin_year)
        forecast_years = tuple(origin + h for h in h3_horizons)
        panel_hist = panel.loc[
            panel["year"].le(origin)
            & panel["training_eligible"]
            & panel["training_gwh"].notna()
        ].copy()
        for p_model in panel_models:
            pred_map = p_model.forecast_panel(
                panel_hist,
                origin,
                forecast_years,
                region_ids,
            )
            for region_id in region_ids:
                scale_hist = history_at_origin(region_frames[region_id], origin)
                for h, target in zip(h3_horizons, forecast_years):
                    _append_record(
                        protocol="recursive_multi_step_h3",
                        model_id=p_model.model_id,
                        region_id=region_id,
                        origin_year=origin,
                        target_year=target,
                        horizon=h,
                        scale_history=scale_hist,
                        raw_prediction=pred_map[(region_id, target)],
                    )
        for region_id in region_ids:
            scale_hist = history_at_origin(region_frames[region_id], origin)
            for s_model in series_models:
                pred_map = s_model.forecast_horizons(
                    scale_hist, origin, forecast_years
                )
                for h, target in zip(h3_horizons, forecast_years):
                    _append_record(
                        protocol="recursive_multi_step_h3",
                        model_id=s_model.model_id,
                        region_id=region_id,
                        origin_year=origin,
                        target_year=target,
                        horizon=h,
                        scale_history=scale_hist,
                        raw_prediction=pred_map[target],
                    )

    # 3. extended_horizon (origins 2018->h1..6, 2019->h1..5, 2020->h1..4)
    for origin, horizons in EXTENDED_ORIGIN_HORIZONS.items():
        forecast_years = tuple(origin + h for h in horizons)
        panel_hist = panel.loc[
            panel["year"].le(origin)
            & panel["training_eligible"]
            & panel["training_gwh"].notna()
        ].copy()
        for p_model in panel_models:
            pred_map = p_model.forecast_panel(
                panel_hist,
                origin,
                forecast_years,
                region_ids,
            )
            for region_id in region_ids:
                scale_hist = history_at_origin(region_frames[region_id], origin)
                for h, target in zip(horizons, forecast_years):
                    _append_record(
                        protocol="extended_horizon",
                        model_id=p_model.model_id,
                        region_id=region_id,
                        origin_year=origin,
                        target_year=target,
                        horizon=h,
                        scale_history=scale_hist,
                        raw_prediction=pred_map[(region_id, target)],
                    )
        for region_id in region_ids:
            scale_hist = history_at_origin(region_frames[region_id], origin)
            for s_model in series_models:
                pred_map = s_model.forecast_horizons(
                    scale_hist, origin, forecast_years
                )
                for h, target in zip(horizons, forecast_years):
                    _append_record(
                        protocol="extended_horizon",
                        model_id=s_model.model_id,
                        region_id=region_id,
                        origin_year=origin,
                        target_year=target,
                        horizon=h,
                        scale_history=scale_hist,
                        raw_prediction=pred_map[target],
                    )

    predictions = pd.DataFrame(rows)
    return predictions.sort_values(
        [
            "protocol",
            "region_id",
            "origin_year",
            "forecast_year",
            "horizon",
            "model",
        ]
    ).reset_index(drop=True)


def run_domain_projections_2025_2030(
    panel: pd.DataFrame,
    config: ProductionConfig,
    *,
    domain: str,
    series_models: tuple[SeriesExperimentModel, ...],
    panel_models: tuple[PanelExperimentModel, ...],
) -> pd.DataFrame:
    """Fit each model on full history up to 2024 and project 2025-2030."""
    origin_year = int(config.history_end_year)
    forecast_years = config.forecast_years
    region_frames: dict[str, pd.DataFrame] = {
        str(rid): group.sort_values("year").reset_index(drop=True)
        for rid, group in panel.groupby("region_id", sort=False)
    }
    region_ids = tuple(region_frames.keys())
    panel_hist = panel.loc[
        panel["year"].le(origin_year)
        & panel["training_eligible"]
        & panel["training_gwh"].notna()
    ].copy()

    rows: list[dict[str, object]] = []

    def _append_proj(
        *,
        model_id: str,
        region_id: str,
        region_name: str,
        modeling_order: int,
        actual_2024: float,
        target_year: int,
        horizon: int,
        raw_prediction: float,
    ) -> None:
        pred, clipped = clip_nonnegative(float(raw_prediction))
        rows.append(
            {
                "domain": domain,
                "model": model_id,
                "region_id": region_id,
                "region_name": region_name,
                "modeling_order": int(modeling_order),
                "origin_year": origin_year,
                "year": int(target_year),
                "horizon": int(horizon),
                "actual_2024_gwh": float(actual_2024),
                "raw_prediction_gwh": float(raw_prediction),
                "prediction_gwh": float(pred),
                "was_clipped_nonnegative": bool(clipped),
            }
        )

    region_meta = {
        rid: (
            str(df.iloc[0]["region_name"]),
            int(df.iloc[0]["modeling_order"]),
            float(
                df.loc[df["year"].eq(origin_year), "actual_gwh"].iloc[0]
            ),
        )
        for rid, df in region_frames.items()
    }

    for p_model in panel_models:
        pred_map = p_model.forecast_panel(
            panel_hist,
            origin_year,
            forecast_years,
            region_ids,
        )
        for region_id in region_ids:
            rname, morder, act24 = region_meta[region_id]
            for h, target_year in enumerate(forecast_years, start=1):
                _append_proj(
                    model_id=p_model.model_id,
                    region_id=region_id,
                    region_name=rname,
                    modeling_order=morder,
                    actual_2024=act24,
                    target_year=int(target_year),
                    horizon=h,
                    raw_prediction=pred_map[(region_id, int(target_year))],
                )

    for region_id in region_ids:
        rname, morder, act24 = region_meta[region_id]
        hist = training_history(region_frames[region_id])
        for s_model in series_models:
            pred_map = s_model.forecast_horizons(hist, origin_year, forecast_years)
            for h, target_year in enumerate(forecast_years, start=1):
                _append_proj(
                    model_id=s_model.model_id,
                    region_id=region_id,
                    region_name=rname,
                    modeling_order=morder,
                    actual_2024=act24,
                    target_year=int(target_year),
                    horizon=h,
                    raw_prediction=pred_map[int(target_year)],
                )

    frame = pd.DataFrame(rows)
    return frame.sort_values(
        ["model", "modeling_order", "year"]
    ).reset_index(drop=True)


def _summarize_slice(
    subset: pd.DataFrame,
    *,
    meta_map: dict[str, ModelMetadata],
    reference_model: str,
    extra_cols: dict[str, object],
) -> list[dict[str, object]]:
    if subset.empty:
        return []
    win_df = win_rate_vs_reference(subset, reference_model=reference_model)
    win_lookup = win_df.set_index(["domain", "protocol", "model"]).to_dict("index")

    out: list[dict[str, object]] = []
    for (domain, protocol, model_id), group in subset.groupby(
        ["domain", "protocol", "model"], sort=True
    ):
        rec = metric_record(group)
        win_info = win_lookup[(domain, protocol, model_id)]
        meta = meta_map[str(model_id)]
        out.append(
            {
                "domain": str(domain),
                **extra_cols,
                "model": str(model_id),
                "model_label": meta.model_label,
                "family": meta.family,
                "is_baseline": meta.is_baseline,
                **rec,
                "comparisons": int(win_info["comparisons"]),
                "wins": int(win_info["wins"]),
                "ties": int(win_info["ties"]),
                "losses": int(win_info["losses"]),
                "win_rate_vs_drift": float(win_info["win_rate_vs_reference"]),
            }
        )
    return out


def build_metrics_summary_table(
    predictions: pd.DataFrame,
    *,
    meta_map: dict[str, ModelMetadata],
    reference_model: str = "drift",
) -> pd.DataFrame:
    slices: list[tuple[str, pd.DataFrame]] = [
        (
            "rolling_one_step",
            predictions.loc[predictions["protocol"].eq("rolling_one_step")],
        ),
        (
            "recursive_multi_step_h3",
            predictions.loc[predictions["protocol"].eq("recursive_multi_step_h3")],
        ),
        (
            "extended_horizon_all_h1_h6",
            predictions.loc[predictions["protocol"].eq("extended_horizon")],
        ),
        (
            "extended_horizon_h4_h6",
            predictions.loc[
                predictions["protocol"].eq("extended_horizon")
                & predictions["horizon"].isin([4, 5, 6])
            ],
        ),
    ]
    rows: list[dict[str, object]] = []
    for order, (slice_name, subset) in enumerate(slices, start=1):
        slice_rows = _summarize_slice(
            subset,
            meta_map=meta_map,
            reference_model=reference_model,
            extra_cols={"protocol_slice": slice_name, "_order": order},
        )
        rows.extend(slice_rows)
    frame = (
        pd.DataFrame(rows)
        .sort_values(["_order", "macro_smape_percent", "macro_mase", "model"])
        .drop(columns=["_order"])
        .reset_index(drop=True)
    )
    return frame


def build_supply_regime_table(
    predictions: pd.DataFrame,
    *,
    meta_map: dict[str, ModelMetadata],
    reference_model: str = "drift",
) -> pd.DataFrame:
    regime_specs = (
        (1, "all_years", "Seluruh Tahun Evaluasi (2019-2024)", lambda df: df["forecast_year"].between(2019, 2024)),
        (2, "pre_2021", "Pra-2021 (2019-2020)", lambda df: df["forecast_year"].isin([2019, 2020])),
        (3, "shock_2021", "Tahun Guncangan 2021 (2021)", lambda df: df["forecast_year"].eq(2021)),
        (4, "post_2021", "Pasca-2021 (2022-2024)", lambda df: df["forecast_year"].isin([2022, 2023, 2024])),
        (
            5,
            "post_2021_clean_origins",
            "Pasca-2021 Origin >= 2021 (2022-2024)",
            lambda df: df["forecast_year"].isin([2022, 2023, 2024]) & df["origin_year"].ge(2021),
        ),
    )
    rows: list[dict[str, object]] = []
    for p_order, protocol in enumerate(("rolling_one_step", "recursive_multi_step_h3"), start=1):
        proto_df = predictions.loc[predictions["protocol"].eq(protocol)]
        for r_order, regime, regime_label, mask_fn in regime_specs:
            subset = proto_df.loc[mask_fn(proto_df)]
            if subset.empty:
                continue
            rows.extend(
                _summarize_slice(
                    subset,
                    meta_map=meta_map,
                    reference_model=reference_model,
                    extra_cols={
                        "protocol": protocol,
                        "regime": regime,
                        "regime_label": regime_label,
                        "_p_order": p_order,
                        "_r_order": r_order,
                    },
                )
            )
    return (
        pd.DataFrame(rows)
        .sort_values(["_p_order", "_r_order", "macro_smape_percent", "macro_mase", "model"])
        .drop(columns=["_p_order", "_r_order"])
        .reset_index(drop=True)
    )


def build_demand_scenario_table(
    predictions: pd.DataFrame,
    *,
    meta_map: dict[str, ModelMetadata],
    reference_model: str = "drift",
) -> pd.DataFrame:
    scenario_specs = (
        (1, "all_observations", "Seluruh Observasi (34 Provinsi)", lambda df: pd.Series(True, index=df.index)),
        (
            2,
            "exclude_kr_2020_target",
            "Tanpa Target Outlier KR 2020",
            lambda df: ~(df["region_id"].eq("KR") & df["forecast_year"].eq(2020)),
        ),
        (
            3,
            "exclude_kr_2020_target_and_origin",
            "Tanpa Target & Origin KR 2020",
            lambda df: ~(
                df["region_id"].eq("KR")
                & (df["forecast_year"].eq(2020) | df["origin_year"].eq(2020))
            ),
        ),
        (
            4,
            "exclude_kr_all_years",
            "Tanpa Provinsi KR (33 Provinsi)",
            lambda df: ~df["region_id"].eq("KR"),
        ),
    )
    protocol_slices = (
        (1, "rolling_one_step", predictions.loc[predictions["protocol"].eq("rolling_one_step")]),
        (2, "recursive_multi_step_h3", predictions.loc[predictions["protocol"].eq("recursive_multi_step_h3")]),
        (
            3,
            "extended_horizon_h4_h6",
            predictions.loc[
                predictions["protocol"].eq("extended_horizon")
                & predictions["horizon"].isin([4, 5, 6])
            ],
        ),
    )
    rows: list[dict[str, object]] = []
    for p_order, slice_name, base_df in protocol_slices:
        for s_order, scenario, scenario_label, mask_fn in scenario_specs:
            subset = base_df.loc[mask_fn(base_df)]
            if subset.empty:
                continue
            rows.extend(
                _summarize_slice(
                    subset,
                    meta_map=meta_map,
                    reference_model=reference_model,
                    extra_cols={
                        "protocol_slice": slice_name,
                        "scenario": scenario,
                        "scenario_label": scenario_label,
                        "_p_order": p_order,
                        "_s_order": s_order,
                    },
                )
            )
    return (
        pd.DataFrame(rows)
        .sort_values(["_p_order", "_s_order", "macro_smape_percent", "macro_mase", "model"])
        .drop(columns=["_p_order", "_s_order"])
        .reset_index(drop=True)
    )


def build_horizon_table(
    predictions: pd.DataFrame,
    *,
    domain: str,
    meta_map: dict[str, ModelMetadata],
    reference_model: str = "drift",
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    specs: list[tuple[int, str, str, pd.DataFrame]] = [
        (
            1,
            "recursive_multi_step_h3",
            "all_observations",
            predictions.loc[predictions["protocol"].eq("recursive_multi_step_h3")],
        ),
        (
            2,
            "extended_horizon",
            "all_observations",
            predictions.loc[predictions["protocol"].eq("extended_horizon")],
        ),
    ]
    if domain == "demand":
        kr_mask = ~(
            predictions["region_id"].eq("KR")
            & (predictions["forecast_year"].eq(2020) | predictions["origin_year"].eq(2020))
        )
        specs.append(
            (
                3,
                "extended_horizon",
                "exclude_kr_2020_target_and_origin",
                predictions.loc[predictions["protocol"].eq("extended_horizon") & kr_mask],
            )
        )
    for order, proto_name, scenario_name, df_slice in specs:
        for horizon, h_group in df_slice.groupby("horizon", sort=True):
            rows.extend(
                _summarize_slice(
                    h_group,
                    meta_map=meta_map,
                    reference_model=reference_model,
                    extra_cols={
                        "protocol_slice": proto_name,
                        "scenario": scenario_name,
                        "horizon": int(horizon),
                        "_order": order,
                    },
                )
            )
    return (
        pd.DataFrame(rows)
        .sort_values(["_order", "horizon", "macro_smape_percent", "macro_mase", "model"])
        .drop(columns=["_order"])
        .reset_index(drop=True)
    )


def _cagr_percent(start_val: float, end_val: float, years: int) -> float:
    if not np.isfinite(start_val) or not np.isfinite(end_val) or start_val <= 0.0 or years <= 0:
        return float("nan")
    if end_val <= 0.0:
        return -100.0
    return float((((end_val / start_val) ** (1.0 / float(years))) - 1.0) * 100.0)


def build_sanity_check_tables(
    projections: pd.DataFrame,
    panel: pd.DataFrame,
    *,
    domain: str,
    meta_map: dict[str, ModelMetadata],
    key_provinces: tuple[str, ...],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    nat_actuals = (
        panel.loc[panel["actual_gwh"].notna()]
        .groupby("year")["actual_gwh"]
        .sum()
        .to_dict()
    )
    nat_2011 = float(nat_actuals[2011])
    nat_2013 = float(nat_actuals[2013])
    nat_2021 = float(nat_actuals[2021])
    nat_2024 = float(nat_actuals[2024])
    hist_cagr_11_24 = _cagr_percent(nat_2011, nat_2024, 13)
    hist_cagr_13_24 = _cagr_percent(nat_2013, nat_2024, 11)
    hist_cagr_21_24 = _cagr_percent(nat_2021, nat_2024, 3)

    nat_rows: list[dict[str, object]] = []
    key_rows: list[dict[str, object]] = []

    for model_id, m_group in projections.groupby("model", sort=False):
        meta = meta_map[str(model_id)]
        y2025 = m_group.loc[m_group["year"].eq(2025)].set_index("region_id")
        y2030 = m_group.loc[m_group["year"].eq(2030)].set_index("region_id")
        clipped_any = m_group.groupby("region_id")["was_clipped_nonnegative"].any().to_dict()

        fcst_nat_2025 = float(y2025["prediction_gwh"].sum())
        fcst_nat_2030 = float(y2030["prediction_gwh"].sum())
        implied_nat_cagr = _cagr_percent(nat_2024, fcst_nat_2030, 6)

        neg_slope_count = 0
        zero_clip_count = 0
        extreme_cagr_count = 0
        reg_cagrs: list[float] = []
        flagged: list[str] = []

        for rid in y2030.index:
            act24 = float(y2030.loc[rid, "actual_2024_gwh"])
            f25 = float(y2025.loc[rid, "prediction_gwh"])
            f30 = float(y2030.loc[rid, "prediction_gwh"])
            was_clip = bool(clipped_any.get(rid, False))
            cagr = _cagr_percent(act24, f30, 6)
            if np.isfinite(cagr):
                reg_cagrs.append(cagr)

            reasons: list[str] = []
            if f30 < act24 - 1e-6:
                neg_slope_count += 1
                reasons.append("neg")
            if was_clip or f30 <= 1e-6:
                zero_clip_count += 1
                reasons.append("zero/clip")
            if np.isfinite(cagr) and (cagr > 20.0 or cagr < -15.0):
                extreme_cagr_count += 1
                reasons.append("extreme")
            if reasons:
                cagr_str = f"{cagr:+.1f}%" if np.isfinite(cagr) else "nan"
                flagged.append(f"{rid}({cagr_str};{'/'.join(reasons)})")

            if rid in key_provinces:
                key_rows.append(
                    {
                        "domain": domain,
                        "model": str(model_id),
                        "model_label": meta.model_label,
                        "region_id": str(rid),
                        "region_name": str(y2030.loc[rid, "region_name"]),
                        "actual_2024_gwh": act24,
                        "forecast_2025_gwh": f25,
                        "forecast_2030_gwh": f30,
                        "implied_cagr_2024_2030_percent": cagr,
                        "was_clipped_any_2025_2030": was_clip,
                    }
                )

        nat_rows.append(
            {
                "domain": domain,
                "model": str(model_id),
                "model_label": meta.model_label,
                "family": meta.family,
                "is_baseline": meta.is_baseline,
                "actual_2024_gwh": nat_2024,
                "forecast_2025_gwh": fcst_nat_2025,
                "forecast_2030_gwh": fcst_nat_2030,
                "implied_cagr_2024_2030_percent": implied_nat_cagr,
                "hist_cagr_2011_2024_percent": hist_cagr_11_24,
                "hist_cagr_2013_2024_percent": hist_cagr_13_24,
                "hist_cagr_2021_2024_percent": hist_cagr_21_24,
                "negative_slope_region_count": neg_slope_count,
                "zero_or_clipped_region_count": zero_clip_count,
                "extreme_cagr_region_count": extreme_cagr_count,
                "min_region_cagr_percent": float(np.min(reg_cagrs)) if reg_cagrs else float("nan"),
                "median_region_cagr_percent": float(np.median(reg_cagrs)) if reg_cagrs else float("nan"),
                "max_region_cagr_percent": float(np.max(reg_cagrs)) if reg_cagrs else float("nan"),
                "flagged_regions": "; ".join(flagged) if flagged else "none",
            }
        )

    nat_df = pd.DataFrame(nat_rows).sort_values(
        ["is_baseline", "model"], ascending=[False, True]
    ).reset_index(drop=True)
    key_order = {rid: idx for idx, rid in enumerate(key_provinces)}
    key_df = pd.DataFrame(key_rows)
    key_df["_kord"] = key_df["region_id"].map(key_order)
    key_df = (
        key_df.sort_values(["model", "_kord"])
        .drop(columns=["_kord"])
        .reset_index(drop=True)
    )
    return nat_df, key_df


def verify_production_baseline_parity(
    predictions: pd.DataFrame,
    production_predictions_path: str | object,
    *,
    domain: str,
) -> list[dict[str, object]]:
    prod = pd.read_csv(production_predictions_path, low_memory=False)
    exp_sub = predictions.loc[
        predictions["protocol"].isin(["rolling_one_step", "recursive_multi_step_h3"])
        & predictions["model"].isin(
            ["naive_lag1", "drift", "moving_average_3", "average_growth_3"]
        )
    ].copy()
    exp_sub["prod_protocol"] = exp_sub["protocol"].replace(
        {"recursive_multi_step_h3": "recursive_multi_step"}
    )

    key_cols = [
        "domain",
        "prod_protocol",
        "model",
        "region_id",
        "origin_year",
        "forecast_year",
        "horizon",
    ]
    prod_cmp = prod.rename(columns={"protocol": "prod_protocol"})
    merged = prod_cmp.merge(
        exp_sub,
        on=key_cols,
        how="outer",
        suffixes=("_prod", "_exp"),
    )
    if len(merged) != len(prod_cmp) or len(exp_sub) != len(prod_cmp):
        raise AssertionError(
            f"{domain} baseline parity row mismatch: prod={len(prod_cmp)}, "
            f"exp={len(exp_sub)}, merged={len(merged)}"
        )

    checks: list[dict[str, object]] = []
    for col in ("prediction_gwh", "smape_percent", "mase"):
        s_prod = pd.to_numeric(merged[f"{col}_prod"], errors="coerce")
        s_exp = pd.to_numeric(merged[f"{col}_exp"], errors="coerce")
        both_na = s_prod.isna() & s_exp.isna()
        if not ((s_prod.notna() & s_exp.notna()) | both_na).all():
            raise AssertionError(f"{domain} baseline parity NaN mismatch on {col}")
        max_diff = float(np.max(np.abs((s_prod - s_exp).dropna()))) if s_prod.notna().any() else 0.0
        if max_diff >= 1e-9:
            raise AssertionError(
                f"{domain} baseline parity failed on {col}: max_diff={max_diff}"
            )
        checks.append(
            {
                "domain": domain,
                "check_name": f"production_baseline_parity_{col}",
                "status": "PASSED",
                "row_count": int(len(merged)),
                "max_abs_diff": max_diff,
                "details": f"Exact match with {len(prod_cmp)} production rows",
            }
        )
    return checks


def verify_zero_leakage(
    panel: pd.DataFrame,
    *,
    domain: str,
    series_models: tuple[SeriesExperimentModel, ...],
    panel_models: tuple[PanelExperimentModel, ...],
) -> list[dict[str, object]]:
    region_ids = tuple(panel["region_id"].drop_duplicates().tolist())
    checks: list[dict[str, object]] = []

    for origin_year, forecast_years in (
        (2020, (2021, 2022, 2023, 2024)),
        (2021, (2022, 2023, 2024)),
    ):
        perturbed = panel.copy()
        future_mask = perturbed["year"] > origin_year
        perturbed.loc[future_mask, "actual_gwh"] = (
            perturbed.loc[future_mask, "actual_gwh"] * 9.99 + 123.45
        )
        perturbed.loc[future_mask, "training_gwh"] = (
            perturbed.loc[future_mask, "training_gwh"] * 9.99 + 123.45
        )

        # Panel history filtered <= origin_year AND unfiltered full panel passed for series checks
        max_diff_all = 0.0
        for s_model in series_models:
            for rid in region_ids:
                h_orig = (
                    panel.loc[
                        panel["region_id"].eq(rid)
                        & panel["training_eligible"]
                        & panel["training_gwh"].notna(),
                        ["year", "training_gwh"],
                    ]
                    .rename(columns={"training_gwh": "target_gwh"})
                    .sort_values("year")
                )
                h_pert = (
                    perturbed.loc[
                        perturbed["region_id"].eq(rid)
                        & perturbed["training_eligible"]
                        & perturbed["training_gwh"].notna(),
                        ["year", "training_gwh"],
                    ]
                    .rename(columns={"training_gwh": "target_gwh"})
                    .sort_values("year")
                )
                p1 = s_model.forecast_horizons(h_orig, origin_year, forecast_years)
                p2 = s_model.forecast_horizons(h_pert, origin_year, forecast_years)
                for y in forecast_years:
                    diff = abs(float(p1[int(y)]) - float(p2[int(y)]))
                    max_diff_all = max(max_diff_all, diff)
                    if diff != 0.0:
                        raise AssertionError(
                            f"Leakage detected for {domain}/{s_model.model_id}/{rid} "
                            f"at origin={origin_year}, year={y}: diff={diff}"
                        )

        for p_model in panel_models:
            ph_orig = panel.loc[
                panel["training_eligible"] & panel["training_gwh"].notna()
            ].copy()
            ph_pert = perturbed.loc[
                perturbed["training_eligible"] & perturbed["training_gwh"].notna()
            ].copy()
            pm1 = p_model.forecast_panel(ph_orig, origin_year, forecast_years, region_ids)
            pm2 = p_model.forecast_panel(ph_pert, origin_year, forecast_years, region_ids)
            for rid in region_ids:
                for y in forecast_years:
                    diff = abs(float(pm1[(rid, int(y))]) - float(pm2[(rid, int(y))]))
                    max_diff_all = max(max_diff_all, diff)
                    if diff != 0.0:
                        raise AssertionError(
                            f"Leakage detected for {domain}/{p_model.model_id}/{rid} "
                            f"at origin={origin_year}, year={y}: diff={diff}"
                        )

        checks.append(
            {
                "domain": domain,
                "check_name": f"zero_leakage_origin_{origin_year}",
                "status": "PASSED",
                "row_count": int(
                    (len(series_models) + len(panel_models))
                    * len(region_ids)
                    * len(forecast_years)
                ),
                "max_abs_diff": float(max_diff_all),
                "details": (
                    f"All {len(series_models) + len(panel_models)} models invariant "
                    f"under 9.99x+123.45 future perturbation (year > {origin_year})"
                ),
            }
        )
    return checks
