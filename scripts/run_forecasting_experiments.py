from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from ecadin_energy.config import PATHS
from ecadin_energy.experiments.common.evaluator import (
    DEMAND_KEY_PROVINCES,
    SUPPLY_KEY_PROVINCES,
    build_demand_scenario_table,
    build_horizon_table,
    build_metrics_summary_table,
    build_sanity_check_tables,
    build_supply_regime_table,
    collect_model_metadata,
    run_domain_backtests,
    run_domain_projections_2025_2030,
    verify_production_baseline_parity,
    verify_zero_leakage,
)
from ecadin_energy.experiments.common.reporting import generate_phase2_report
from ecadin_energy.experiments.demand import build_demand_models
from ecadin_energy.experiments.supply import build_supply_models
from ecadin_energy.forecasting.configuration import load_production_config
from ecadin_energy.forecasting.production.artifacts import (
    write_csv_deterministic,
)


def _environment_inventory() -> pd.DataFrame:
    packages = ("numpy", "pandas", "scipy", "statsmodels", "sklearn")
    rows: list[dict[str, object]] = [
        {
            "package": "python",
            "installed": True,
            "version": sys.version.split()[0],
            "usage_note": "Runtime interpreter",
        }
    ]
    for pkg in packages:
        try:
            mod = __import__(pkg)
            rows.append(
                {
                    "package": pkg,
                    "installed": True,
                    "version": str(getattr(mod, "__version__", "unknown")),
                    "usage_note": "Installed in environment",
                }
            )
        except ImportError:
            rows.append(
                {
                    "package": pkg,
                    "installed": False,
                    "version": "NOT_INSTALLED",
                    "usage_note": "Implemented cleanly with numpy/scipy",
                }
            )
    return pd.DataFrame(rows)


def _print_compact_table(title: str, df: pd.DataFrame, columns: list[str]) -> None:
    print(f"\n=== {title} ===")
    print(df[columns].to_string(index=False))


def run_experiments(
    *,
    project_root: str | Path | None = None,
    output_dir: str | Path | None = None,
    report_path: str | Path | None = None,
    skip_report: bool = False,
) -> dict[str, Path]:
    root = Path(project_root).resolve() if project_root else PATHS.root
    out_dir = (
        Path(output_dir).resolve()
        if output_dir is not None
        else root / "outputs/experiments"
    )
    resolved_report_path = (
        Path(report_path).resolve()
        if report_path is not None
        else root / "outputs/reports/phase2_forecasting_experiments.txt"
    )
    config = load_production_config(project_root=root)

    supply_panel = pd.read_csv(
        root / "data/processed/modeling/supply_modeling_panel.csv",
        low_memory=False,
    )
    demand_panel = pd.read_csv(
        root / "data/processed/modeling/demand_modeling_panel.csv",
        low_memory=False,
    )

    env_df = _environment_inventory()
    supply_series, supply_panel_models = build_supply_models()
    demand_series, demand_panel_models = build_demand_models()

    supply_meta = collect_model_metadata(supply_series, supply_panel_models)
    demand_meta = collect_model_metadata(demand_series, demand_panel_models)

    supply_preds = run_domain_backtests(
        supply_panel,
        config,
        domain="supply",
        series_models=supply_series,
        panel_models=supply_panel_models,
    )
    demand_preds = run_domain_backtests(
        demand_panel,
        config,
        domain="demand",
        series_models=demand_series,
        panel_models=demand_panel_models,
    )

    # Automated parity & leakage assertions
    self_checks: list[dict[str, object]] = []
    self_checks.extend(
        verify_production_baseline_parity(
            supply_preds,
            root / "outputs/production/backtests/supply_predictions.csv",
            domain="supply",
        )
    )
    self_checks.extend(
        verify_production_baseline_parity(
            demand_preds,
            root / "outputs/production/backtests/demand_predictions.csv",
            domain="demand",
        )
    )
    self_checks.extend(
        verify_zero_leakage(
            supply_panel,
            domain="supply",
            series_models=supply_series,
            panel_models=supply_panel_models,
        )
    )
    self_checks.extend(
        verify_zero_leakage(
            demand_panel,
            domain="demand",
            series_models=demand_series,
            panel_models=demand_panel_models,
        )
    )
    checks_df = pd.DataFrame(self_checks)

    supply_summary = build_metrics_summary_table(
        supply_preds, meta_map=supply_meta, reference_model=config.reference_baseline
    )
    demand_summary = build_metrics_summary_table(
        demand_preds, meta_map=demand_meta, reference_model=config.reference_baseline
    )

    supply_regime = build_supply_regime_table(
        supply_preds, meta_map=supply_meta, reference_model=config.reference_baseline
    )
    demand_scenario = build_demand_scenario_table(
        demand_preds, meta_map=demand_meta, reference_model=config.reference_baseline
    )

    supply_horizon = build_horizon_table(
        supply_preds,
        domain="supply",
        meta_map=supply_meta,
        reference_model=config.reference_baseline,
    )
    demand_horizon = build_horizon_table(
        demand_preds,
        domain="demand",
        meta_map=demand_meta,
        reference_model=config.reference_baseline,
    )

    supply_proj = run_domain_projections_2025_2030(
        supply_panel,
        config,
        domain="supply",
        series_models=supply_series,
        panel_models=supply_panel_models,
    )
    demand_proj = run_domain_projections_2025_2030(
        demand_panel,
        config,
        domain="demand",
        series_models=demand_series,
        panel_models=demand_panel_models,
    )

    supply_nat_sanity, supply_key_sanity = build_sanity_check_tables(
        supply_proj,
        supply_panel,
        domain="supply",
        meta_map=supply_meta,
        key_provinces=SUPPLY_KEY_PROVINCES,
    )
    demand_nat_sanity, demand_key_sanity = build_sanity_check_tables(
        demand_proj,
        demand_panel,
        domain="demand",
        meta_map=demand_meta,
        key_provinces=DEMAND_KEY_PROVINCES,
    )

    outputs: dict[str, tuple[Path, pd.DataFrame]] = {
        "environment_inventory": (
            out_dir / "experiment_environment_inventory.csv",
            env_df,
        ),
        "self_checks": (
            out_dir / "experiment_self_checks.csv",
            checks_df,
        ),
        "supply_predictions": (
            out_dir / "supply_experiment_predictions.csv",
            supply_preds,
        ),
        "demand_predictions": (
            out_dir / "demand_experiment_predictions.csv",
            demand_preds,
        ),
        "supply_metrics_summary": (
            out_dir / "supply_metrics_summary.csv",
            supply_summary,
        ),
        "demand_metrics_summary": (
            out_dir / "demand_metrics_summary.csv",
            demand_summary,
        ),
        "supply_metrics_by_regime": (
            out_dir / "supply_metrics_by_regime.csv",
            supply_regime,
        ),
        "demand_metrics_by_scenario": (
            out_dir / "demand_metrics_by_scenario.csv",
            demand_scenario,
        ),
        "supply_metrics_by_horizon": (
            out_dir / "supply_metrics_by_horizon.csv",
            supply_horizon,
        ),
        "demand_metrics_by_horizon": (
            out_dir / "demand_metrics_by_horizon.csv",
            demand_horizon,
        ),
        "supply_projection_2025_2030": (
            out_dir / "supply_projection_2025_2030_all_regions.csv",
            supply_proj,
        ),
        "demand_projection_2025_2030": (
            out_dir / "demand_projection_2025_2030_all_regions.csv",
            demand_proj,
        ),
        "supply_sanity_check_national": (
            out_dir / "supply_sanity_check_national.csv",
            supply_nat_sanity,
        ),
        "demand_sanity_check_national": (
            out_dir / "demand_sanity_check_national.csv",
            demand_nat_sanity,
        ),
        "supply_sanity_check_key_provinces": (
            out_dir / "supply_sanity_check_key_provinces.csv",
            supply_key_sanity,
        ),
        "demand_sanity_check_key_provinces": (
            out_dir / "demand_sanity_check_key_provinces.csv",
            demand_key_sanity,
        ),
    }

    written: dict[str, Path] = {}
    for key, (path, frame) in outputs.items():
        write_csv_deterministic(frame, path)
        written[key] = path

    if not skip_report:
        generated_report = generate_phase2_report(
            report_path=resolved_report_path,
            env_df=env_df,
            checks_df=checks_df,
            supply_panel=supply_panel,
            demand_panel=demand_panel,
            supply_summary=supply_summary,
            demand_summary=demand_summary,
            supply_regime=supply_regime,
            demand_scenario=demand_scenario,
            supply_horizon=supply_horizon,
            demand_horizon=demand_horizon,
            supply_nat_sanity=supply_nat_sanity,
            demand_nat_sanity=demand_nat_sanity,
            supply_key_sanity=supply_key_sanity,
            demand_key_sanity=demand_key_sanity,
        )
        written["phase2_report"] = generated_report

    _print_compact_table(
        "ENVIRONMENT INVENTORY",
        env_df,
        ["package", "installed", "version"],
    )
    _print_compact_table(
        "AUTOMATED PARITY & ZERO-LEAKAGE CHECKS",
        checks_df,
        ["domain", "check_name", "status", "row_count", "max_abs_diff"],
    )
    _print_compact_table(
        "SUPPLY METRICS SUMMARY",
        supply_summary,
        [
            "protocol_slice",
            "model",
            "macro_smape_percent",
            "macro_mase",
            "mase_valid_prediction_count",
            "micro_rmse_gwh",
            "aggregate_bias_percent",
            "win_rate_vs_drift",
        ],
    )
    _print_compact_table(
        "SUPPLY REGIME STRATIFICATION (POST-2021)",
        supply_regime.loc[
            supply_regime["regime"].isin(["post_2021", "post_2021_clean_origins"])
        ],
        [
            "protocol",
            "regime",
            "model",
            "macro_smape_percent",
            "macro_mase",
            "micro_rmse_gwh",
            "aggregate_bias_percent",
            "win_rate_vs_drift",
        ],
    )
    _print_compact_table(
        "DEMAND METRICS SUMMARY",
        demand_summary,
        [
            "protocol_slice",
            "model",
            "macro_smape_percent",
            "macro_mase",
            "mase_valid_prediction_count",
            "micro_rmse_gwh",
            "aggregate_bias_percent",
            "win_rate_vs_drift",
        ],
    )
    _print_compact_table(
        "DEMAND SCENARIO (EXCL KR 2020 TARGET & ORIGIN)",
        demand_scenario.loc[
            demand_scenario["scenario"].eq("exclude_kr_2020_target_and_origin")
        ],
        [
            "protocol_slice",
            "model",
            "macro_smape_percent",
            "macro_mase",
            "micro_rmse_gwh",
            "aggregate_bias_percent",
            "win_rate_vs_drift",
        ],
    )
    _print_compact_table(
        "SUPPLY 2025-2030 SANITY CHECK (NATIONAL)",
        supply_nat_sanity,
        [
            "model",
            "actual_2024_gwh",
            "forecast_2030_gwh",
            "implied_cagr_2024_2030_percent",
            "negative_slope_region_count",
            "zero_or_clipped_region_count",
            "extreme_cagr_region_count",
        ],
    )
    _print_compact_table(
        "DEMAND 2025-2030 SANITY CHECK (NATIONAL)",
        demand_nat_sanity,
        [
            "model",
            "actual_2024_gwh",
            "forecast_2030_gwh",
            "implied_cagr_2024_2030_percent",
            "negative_slope_region_count",
            "zero_or_clipped_region_count",
            "extreme_cagr_region_count",
        ],
    )

    return written


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run isolated Phase 2 Supply & Demand forecasting experiments."
    )
    parser.add_argument("--project-root", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--report-path", type=Path, default=None)
    parser.add_argument("--skip-report", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    run_experiments(
        project_root=args.project_root,
        output_dir=args.output_dir,
        report_path=args.report_path,
        skip_report=args.skip_report,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
