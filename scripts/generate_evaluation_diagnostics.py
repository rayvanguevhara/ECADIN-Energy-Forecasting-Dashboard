from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from ecadin_energy.config import PATHS
from ecadin_energy.forecasting.evaluation.aggregation import metric_record
from ecadin_energy.forecasting.production.artifacts import (
    write_csv_deterministic,
)


REGIME_SPECS: tuple[
    tuple[int, str, str, str, str, Callable[[pd.DataFrame], pd.Series]],
    ...,
] = (
    (
        1,
        "pre_2021",
        "Pra-2021 (2019-2020)",
        "2019-2020",
        "all_configured",
        lambda df: df["forecast_year"].isin([2019, 2020]),
    ),
    (
        2,
        "shock_2021",
        "Tahun Guncangan 2021 (2021)",
        "2021",
        "all_configured",
        lambda df: df["forecast_year"].eq(2021),
    ),
    (
        3,
        "post_2021",
        "Pasca-2021 (2022-2024)",
        "2022-2024",
        "all_configured",
        lambda df: df["forecast_year"].isin([2022, 2023, 2024]),
    ),
    (
        4,
        "post_2021_clean_origins",
        "Pasca-2021 Origin >= 2021 (2022-2024)",
        "2022-2024",
        "origin_year >= 2021",
        lambda df: (
            df["forecast_year"].isin([2022, 2023, 2024])
            & df["origin_year"].ge(2021)
        ),
    ),
    (
        5,
        "all_years",
        "Seluruh Tahun Evaluasi (2019-2024)",
        "2019-2024",
        "all_configured",
        lambda df: df["forecast_year"].between(2019, 2024),
    ),
)

DEMAND_SCENARIO_SPECS: tuple[
    tuple[int, str, str, Callable[[pd.DataFrame], pd.Series]],
    ...,
] = (
    (
        1,
        "all_observations",
        "Seluruh Observasi (34 Provinsi)",
        lambda df: pd.Series(True, index=df.index),
    ),
    (
        2,
        "exclude_kr_2020_target",
        "Tanpa Target Outlier KR 2020",
        lambda df: ~(
            df["region_id"].eq("KR") & df["forecast_year"].eq(2020)
        ),
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


def _safe_pct_change(prev: float, curr: float) -> float:
    if pd.isna(prev) or pd.isna(curr) or prev == 0.0:
        return float("nan")
    return 100.0 * (float(curr) - float(prev)) / abs(float(prev))


def _drift_smape_pair(
    predictions: pd.DataFrame,
    region_id: str,
    year: int,
) -> tuple[float, float]:
    subset = predictions.loc[
        predictions["model"].eq("drift")
        & predictions["region_id"].eq(region_id)
        & predictions["forecast_year"].eq(year)
    ]
    one_step = subset.loc[
        subset["protocol"].eq("rolling_one_step"), "smape_percent"
    ]
    recursive = subset.loc[
        subset["protocol"].eq("recursive_multi_step"), "smape_percent"
    ]
    one_val = float(one_step.mean()) if not one_step.empty else float("nan")
    rec_val = float(recursive.mean()) if not recursive.empty else float("nan")
    return one_val, rec_val


def build_supply_regime_stratification(
    supply_predictions: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for (
        regime_order,
        regime,
        regime_label,
        forecast_years,
        origin_filter,
        mask_fn,
    ) in REGIME_SPECS:
        filtered = supply_predictions.loc[mask_fn(supply_predictions)]
        for (protocol, model), group in filtered.groupby(
            ["protocol", "model"], sort=True
        ):
            rows.append(
                {
                    "domain": "supply",
                    "protocol": str(protocol),
                    "regime": regime,
                    "regime_label": regime_label,
                    "forecast_years": forecast_years,
                    "origin_filter": origin_filter,
                    "model": str(model),
                    "_regime_order": regime_order,
                    **metric_record(group),
                }
            )
    frame = (
        pd.DataFrame(rows)
        .sort_values(
            ["protocol", "_regime_order", "macro_smape_percent", "model"]
        )
        .drop(columns=["_regime_order"])
        .reset_index(drop=True)
    )
    return frame


def build_demand_sensitivity_kr2020(
    demand_predictions: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    protocol_totals = (
        demand_predictions.groupby("protocol")["model"]
        .count()
        .to_dict()
    )
    baseline_metrics: dict[tuple[str, str], dict[str, float]] = {}

    for scenario_order, scenario, scenario_label, mask_fn in DEMAND_SCENARIO_SPECS:
        mask = mask_fn(demand_predictions)
        filtered = demand_predictions.loc[mask]
        full_counts = (
            demand_predictions.groupby(["protocol", "model"]).size().to_dict()
        )
        for (protocol, model), group in filtered.groupby(
            ["protocol", "model"], sort=True
        ):
            rec = metric_record(group)
            key = (str(protocol), str(model))
            if scenario == "all_observations":
                baseline_metrics[key] = {
                    "macro_smape_percent": float(rec["macro_smape_percent"]),
                    "macro_mase": float(rec["macro_mase"]),
                    "micro_rmse_gwh": float(rec["micro_rmse_gwh"]),
                }
            base = baseline_metrics[key]
            excluded_count = int(full_counts[key]) - int(rec["prediction_count"])
            rows.append(
                {
                    "domain": "demand",
                    "protocol": str(protocol),
                    "scenario": scenario,
                    "scenario_label": scenario_label,
                    "excluded_prediction_count": excluded_count,
                    "model": str(model),
                    "_scenario_order": scenario_order,
                    **rec,
                    "delta_macro_smape_pp": (
                        float(rec["macro_smape_percent"])
                        - base["macro_smape_percent"]
                    ),
                    "delta_macro_mase": (
                        float(rec["macro_mase"]) - base["macro_mase"]
                    ),
                    "delta_micro_rmse_gwh": (
                        float(rec["micro_rmse_gwh"]) - base["micro_rmse_gwh"]
                    ),
                }
            )
    _ = protocol_totals
    frame = (
        pd.DataFrame(rows)
        .sort_values(
            ["protocol", "_scenario_order", "macro_smape_percent", "model"]
        )
        .drop(columns=["_scenario_order"])
        .reset_index(drop=True)
    )
    return frame


def build_data_quality_flag_impact_summary(
    *,
    flags: pd.DataFrame,
    master: pd.DataFrame,
    regions: pd.DataFrame,
    demand_predictions: pd.DataFrame,
    supply_predictions: pd.DataFrame,
) -> pd.DataFrame:
    master_indexed = master.set_index(["region_id", "year"])
    region_lookup = regions.set_index("region_id")[
        ["display_name", "island_group"]
    ].to_dict("index")
    cap_flag_keys = set(
        zip(
            flags.loc[
                flags["dataset_id"].eq("supply_installed_capacity")
                & flags["issue_type"].eq("large_consecutive_yoy_change"),
                "region_id",
            ].astype(str),
            pd.to_numeric(
                flags.loc[
                    flags["dataset_id"].eq("supply_installed_capacity")
                    & flags["issue_type"].eq("large_consecutive_yoy_change"),
                    "year",
                ],
                errors="coerce",
            )
            .fillna(-1)
            .astype(int),
        )
    )

    supply_2021_flags = flags.loc[
        flags["dataset_id"].eq("supply_local_generation")
        & flags["year"].eq(2021)
        & flags["issue_type"].eq("large_consecutive_yoy_change")
    ].copy()

    supply_rows: list[dict[str, object]] = []
    for record in supply_2021_flags.to_dict("records"):
        region_id = str(record["region_id"])
        year = int(record["year"])
        prev_val = float(master_indexed.loc[(region_id, year - 1), "local_generation_gwh"])
        curr_val = float(master_indexed.loc[(region_id, year), "local_generation_gwh"])
        cap_prev = float(master_indexed.loc[(region_id, year - 1), "installed_capacity_mw"])
        cap_curr = float(master_indexed.loc[(region_id, year), "installed_capacity_mw"])
        one_smape, rec_smape = _drift_smape_pair(supply_predictions, region_id, year)
        meta = region_lookup[region_id]
        supply_rows.append(
            {
                "category": "supply_2021_structural_break",
                "domain": "supply",
                "region_id": region_id,
                "region_name": str(meta["display_name"]),
                "island_group": str(meta["island_group"]),
                "year": year,
                "variable_name": "local_generation_gwh",
                "flagged_in_quality_table": True,
                "issue_type": str(record["issue_type"]),
                "prev_year_value": prev_val,
                "observed_value": curr_val,
                "abs_change": curr_val - prev_val,
                "yoy_change_percent": float(record["metric_value"]),
                "installed_capacity_prev_mw": cap_prev,
                "installed_capacity_mw": cap_curr,
                "installed_capacity_yoy_percent": _safe_pct_change(cap_prev, cap_curr),
                "installed_capacity_flagged_same_year": (region_id, year)
                in cap_flag_keys,
                "drift_one_step_smape_percent": one_smape,
                "drift_recursive_mean_smape_percent": rec_smape,
                "diagnostic_note": (
                    "Flagged >=75% & >=100 GWh supply structural break in 2021."
                ),
            }
        )

    # Document Sulawesi Barat (SR): 0.00 -> 249.45 GWh in 2021 (zero denominator skips YoY ratio rule).
    sr_prev = float(master_indexed.loc[("SR", 2020), "local_generation_gwh"])
    sr_curr = float(master_indexed.loc[("SR", 2021), "local_generation_gwh"])
    sr_cap_prev = float(master_indexed.loc[("SR", 2020), "installed_capacity_mw"])
    sr_cap_curr = float(master_indexed.loc[("SR", 2021), "installed_capacity_mw"])
    sr_one_smape, sr_rec_smape = _drift_smape_pair(supply_predictions, "SR", 2021)
    sr_meta = region_lookup["SR"]
    supply_rows.append(
        {
            "category": "supply_2021_structural_break",
            "domain": "supply",
            "region_id": "SR",
            "region_name": str(sr_meta["display_name"]),
            "island_group": str(sr_meta["island_group"]),
            "year": 2021,
            "variable_name": "local_generation_gwh",
            "flagged_in_quality_table": False,
            "issue_type": "unflagged_zero_base_jump",
            "prev_year_value": sr_prev,
            "observed_value": sr_curr,
            "abs_change": sr_curr - sr_prev,
            "yoy_change_percent": float("nan"),
            "installed_capacity_prev_mw": sr_cap_prev,
            "installed_capacity_mw": sr_cap_curr,
            "installed_capacity_yoy_percent": _safe_pct_change(
                sr_cap_prev, sr_cap_curr
            ),
            "installed_capacity_flagged_same_year": ("SR", 2021)
            in cap_flag_keys,
            "drift_one_step_smape_percent": sr_one_smape,
            "drift_recursive_mean_smape_percent": sr_rec_smape,
            "diagnostic_note": (
                "Zero-base 2021 jump (0.00 -> 249.45 GWh); omitted from "
                "percentage YoY flag rule because 2020 baseline is 0."
            ),
        }
    )

    supply_df = (
        pd.DataFrame(supply_rows)
        .sort_values("yoy_change_percent", ascending=False, na_position="last")
        .reset_index(drop=True)
    )

    demand_flags = flags.loc[
        flags["dataset_id"].eq("demand_distributed_electricity")
        & flags["issue_type"].eq("large_consecutive_yoy_change")
    ].copy()
    demand_rows: list[dict[str, object]] = []
    for record in demand_flags.to_dict("records"):
        region_id = str(record["region_id"])
        year = int(record["year"])
        prev_val = float(
            master_indexed.loc[
                (region_id, year - 1), "distributed_electricity_gwh"
            ]
        )
        curr_val = float(
            master_indexed.loc[(region_id, year), "distributed_electricity_gwh"]
        )
        cap_prev = float(
            master_indexed.loc[(region_id, year - 1), "installed_capacity_mw"]
        )
        cap_curr = float(
            master_indexed.loc[(region_id, year), "installed_capacity_mw"]
        )
        one_smape, rec_smape = _drift_smape_pair(
            demand_predictions, region_id, year
        )
        meta = region_lookup[region_id]
        yoy_val = float(record["metric_value"])
        demand_rows.append(
            {
                "category": "demand_yoy_anomaly",
                "domain": "demand",
                "region_id": region_id,
                "region_name": str(meta["display_name"]),
                "island_group": str(meta["island_group"]),
                "year": year,
                "variable_name": "distributed_electricity_gwh",
                "flagged_in_quality_table": True,
                "issue_type": str(record["issue_type"]),
                "prev_year_value": prev_val,
                "observed_value": curr_val,
                "abs_change": curr_val - prev_val,
                "yoy_change_percent": yoy_val,
                "installed_capacity_prev_mw": cap_prev,
                "installed_capacity_mw": cap_curr,
                "installed_capacity_yoy_percent": _safe_pct_change(
                    cap_prev, cap_curr
                ),
                "installed_capacity_flagged_same_year": (region_id, year)
                in cap_flag_keys,
                "drift_one_step_smape_percent": one_smape,
                "drift_recursive_mean_smape_percent": rec_smape,
                "diagnostic_note": (
                    "Single-year demand contraction (-73.5%) distorting KR backtests."
                    if region_id == "KR" and year == 2020
                    else (
                        "Post-2020 rebound (+291.9%) following KR 2020 dip."
                        if region_id == "KR" and year == 2021
                        else "Flagged >=35% consecutive demand YoY change."
                    )
                ),
            }
        )

    demand_df = pd.DataFrame(demand_rows)
    demand_df["_abs_yoy"] = demand_df["yoy_change_percent"].abs()
    demand_df = (
        demand_df.sort_values(["_abs_yoy", "region_id"], ascending=[False, True])
        .drop(columns=["_abs_yoy"])
        .reset_index(drop=True)
    )

    return pd.concat([supply_df, demand_df], ignore_index=True)


def generate_diagnostics(
    *,
    project_root: str | Path | None = None,
    output_dir: str | Path | None = None,
) -> dict[str, Path]:
    root = Path(project_root).resolve() if project_root else PATHS.root
    out = (
        Path(output_dir).resolve()
        if output_dir is not None
        else root / "outputs/reports/analysis"
    )
    flags = pd.read_csv(
        root / "data/processed/master/data_quality_flags.csv",
        low_memory=False,
    )
    master = pd.read_csv(
        root / "data/processed/master/regional_energy_master.csv",
        low_memory=False,
    )
    regions = pd.read_csv(
        root / "data/reference/regions.csv",
        low_memory=False,
    )
    demand_predictions = pd.read_csv(
        root / "outputs/production/backtests/demand_predictions.csv",
        low_memory=False,
    )
    supply_predictions = pd.read_csv(
        root / "outputs/production/backtests/supply_predictions.csv",
        low_memory=False,
    )

    stratification = build_supply_regime_stratification(supply_predictions)
    kr_sensitivity = build_demand_sensitivity_kr2020(demand_predictions)
    flag_impact = build_data_quality_flag_impact_summary(
        flags=flags,
        master=master,
        regions=regions,
        demand_predictions=demand_predictions,
        supply_predictions=supply_predictions,
    )

    written = {
        "supply_regime_stratification": out
        / "supply_regime_stratification.csv",
        "demand_sensitivity_kr2020": out / "demand_sensitivity_kr2020.csv",
        "data_quality_flag_impact_summary": out
        / "data_quality_flag_impact_summary.csv",
    }
    write_csv_deterministic(
        stratification, written["supply_regime_stratification"]
    )
    write_csv_deterministic(kr_sensitivity, written["demand_sensitivity_kr2020"])
    write_csv_deterministic(
        flag_impact, written["data_quality_flag_impact_summary"]
    )
    return written


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate read-only D-2 evaluation diagnostic tables under "
            "outputs/reports/analysis/ without modifying production hashes."
        )
    )
    parser.add_argument("--project-root", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    written = generate_diagnostics(
        project_root=args.project_root,
        output_dir=args.output_dir,
    )
    print("ECADIN EVALUATION DIAGNOSTICS (D-2): GENERATED")
    for key, path in written.items():
        frame = pd.read_csv(path, low_memory=False)
        print(f"- {key}: {path} ({len(frame)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
