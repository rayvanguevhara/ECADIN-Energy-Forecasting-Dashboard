from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from ecadin_energy.config import PATHS
from ecadin_energy.forecasting.backtesting.runner import run_backtests
from ecadin_energy.forecasting.configuration import (
    ProductionConfig,
    load_production_config,
)
from ecadin_energy.forecasting.data.loaders import (
    load_regional_master,
    load_regions,
)
from ecadin_energy.forecasting.data.panels import (
    build_demand_panel,
    build_supply_panel,
)
from ecadin_energy.forecasting.data.validation import (
    validate_modeling_panel,
)
from ecadin_energy.forecasting.production.accounting import (
    build_accounting_difference,
    build_combined_history_forecast,
)
from ecadin_energy.forecasting.production.artifacts import (
    relative_posix_path,
    sha256_file,
    write_csv_deterministic,
    write_json,
)
from ecadin_energy.forecasting.production.demand import (
    build_demand_forecast,
)
from ecadin_energy.forecasting.production.supply import (
    build_supply_forecast,
)
from ecadin_energy.forecasting.production.validation import (
    validate_production_frames,
)


def _root(project_root: str | Path | None) -> Path:
    return Path(project_root).resolve() if project_root else PATHS.root


def _output_paths(root: Path) -> dict[str, Path]:
    return {
        "demand_panel": root
        / "data/processed/modeling/demand_modeling_panel.csv",
        "supply_panel": root
        / "data/processed/modeling/supply_modeling_panel.csv",
        "demand_predictions": root
        / "outputs/production/backtests/demand_predictions.csv",
        "supply_predictions": root
        / "outputs/production/backtests/supply_predictions.csv",
        "demand_metrics": root
        / "outputs/production/metrics/demand_metrics_summary.csv",
        "supply_metrics": root
        / "outputs/production/metrics/supply_metrics_summary.csv",
        "demand_metrics_by_fold": root
        / "outputs/production/metrics/demand_metrics_by_fold.csv",
        "supply_metrics_by_fold": root
        / "outputs/production/metrics/supply_metrics_by_fold.csv",
        "demand_metrics_by_horizon": root
        / "outputs/production/metrics/demand_metrics_by_horizon.csv",
        "supply_metrics_by_horizon": root
        / "outputs/production/metrics/supply_metrics_by_horizon.csv",
        "demand_metrics_by_region": root
        / "outputs/production/metrics/demand_metrics_by_region.csv",
        "supply_metrics_by_region": root
        / "outputs/production/metrics/supply_metrics_by_region.csv",
        "demand_win_rate": root
        / "outputs/production/metrics/demand_win_rate_vs_drift.csv",
        "supply_win_rate": root
        / "outputs/production/metrics/supply_win_rate_vs_drift.csv",
        "demand_win_rate_by_horizon": root
        / "outputs/production/metrics/demand_win_rate_by_horizon_vs_drift.csv",
        "supply_win_rate_by_horizon": root
        / "outputs/production/metrics/supply_win_rate_by_horizon_vs_drift.csv",
        "demand_win_rate_by_regime": root
        / "outputs/production/metrics/demand_win_rate_by_regime_vs_drift.csv",
        "supply_win_rate_by_regime": root
        / "outputs/production/metrics/supply_win_rate_by_regime_vs_drift.csv",
        "model_summary": root
        / "outputs/production/metrics/production_model_summary.csv",
        "demand_forecast": root
        / "outputs/production/forecasts/demand_forecast.csv",
        "supply_forecast": root
        / "outputs/production/forecasts/supply_forecast.csv",
        "supply_calibration": root
        / "outputs/production/forecasts/supply_uncertainty_calibration.csv",
        "demand_history_summary": root
        / "outputs/production/forecasts/demand_history_summary.csv",
        "supply_history_summary": root
        / "outputs/production/forecasts/supply_history_summary.csv",
        "accounting": root
        / "outputs/production/accounting/accounting_difference.csv",
        "combined": root
        / "outputs/production/combined/regional_energy_history_forecast.csv",
        "checks": root
        / "outputs/production/reports/production_contract_checks.csv",
        "input_hashes": root
        / "outputs/production/reports/production_input_hashes.csv",
        "summary": root
        / "outputs/production/reports/production_run_summary.json",
    }


def _model_summary(
    demand_metrics: pd.DataFrame,
    supply_metrics: pd.DataFrame,
    config: ProductionConfig,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for domain, metrics, domain_config in (
        ("demand", demand_metrics, config.demand),
        ("supply", supply_metrics, config.supply),
    ):
        selected = metrics.loc[
            metrics["model"].eq(config.reference_baseline)
        ]
        for record in selected.to_dict("records"):
            rows.append(
                {
                    "domain": domain,
                    "production_model_id": domain_config.production_model_id,
                    "model_label": domain_config.model_label,
                    "protocol": record["protocol"],
                    "prediction_count": record["prediction_count"],
                    "macro_smape_percent": record[
                        "macro_smape_percent"
                    ],
                    "macro_mase": record["macro_mase"],
                    "micro_rmse_gwh": record["micro_rmse_gwh"],
                    "aggregate_bias_percent": record[
                        "aggregate_bias_percent"
                    ],
                    "selected_for_production": True,
                    "selection_note": (
                        "Validated production contract; challengers remain "
                        "experiments and are not auto-promoted."
                    ),
                }
            )
    return pd.DataFrame(rows)


def _input_hashes(
    root: Path,
    config_path: Path,
) -> pd.DataFrame:
    inputs = [
        (
            "regional_energy_master",
            root / "data/processed/master/regional_energy_master.csv",
        ),
        ("regions", root / "data/reference/regions.csv"),
        ("production_config", config_path),
    ]
    rows: list[dict[str, object]] = []
    for input_id, path in inputs:
        rows.append(
            {
                "input_id": input_id,
                "relative_path": relative_posix_path(path, root),
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
        )
    return pd.DataFrame(rows)


def run_production_pipeline(
    *,
    project_root: str | Path | None = None,
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    root = _root(project_root)
    resolved_config_path = (
        Path(config_path)
        if config_path is not None
        else root / "configs/forecasting/production.json"
    )
    if not resolved_config_path.is_absolute():
        resolved_config_path = root / resolved_config_path
    config = load_production_config(
        resolved_config_path,
        project_root=root,
    )
    master = load_regional_master(project_root=root)
    regions = load_regions(project_root=root)

    demand_panel = build_demand_panel(master, regions, config)
    supply_panel = build_supply_panel(master, regions, config)
    demand_panel_contract = validate_modeling_panel(
        demand_panel,
        config,
        domain="demand",
    )
    supply_panel_contract = validate_modeling_panel(
        supply_panel,
        config,
        domain="supply",
    )

    demand_backtests = run_backtests(
        demand_panel,
        config,
        domain="demand",
    )
    supply_backtests = run_backtests(
        supply_panel,
        config,
        domain="supply",
    )

    demand_forecast, demand_history = build_demand_forecast(
        demand_panel,
        config,
    )
    (
        supply_forecast,
        supply_calibration,
        supply_history,
    ) = build_supply_forecast(
        supply_panel,
        supply_backtests["predictions"],
        config,
    )
    accounting = build_accounting_difference(
        demand_forecast,
        supply_forecast,
        config,
    )
    combined = build_combined_history_forecast(
        demand_panel,
        supply_panel,
        accounting,
        config,
    )
    checks = validate_production_frames(
        demand_panel=demand_panel,
        supply_panel=supply_panel,
        demand_backtest=demand_backtests["predictions"],
        supply_backtest=supply_backtests["predictions"],
        demand_forecast=demand_forecast,
        supply_forecast=supply_forecast,
        accounting=accounting,
        combined=combined,
        config=config,
    )
    model_summary = _model_summary(
        demand_backtests["metrics_summary"],
        supply_backtests["metrics_summary"],
        config,
    )
    paths = _output_paths(root)

    frames = {
        "demand_panel": demand_panel,
        "supply_panel": supply_panel,
        "demand_predictions": demand_backtests["predictions"],
        "supply_predictions": supply_backtests["predictions"],
        "demand_metrics": demand_backtests["metrics_summary"],
        "supply_metrics": supply_backtests["metrics_summary"],
        "demand_metrics_by_fold": demand_backtests["metrics_by_fold"],
        "supply_metrics_by_fold": supply_backtests["metrics_by_fold"],
        "demand_metrics_by_horizon": demand_backtests[
            "metrics_by_horizon"
        ],
        "supply_metrics_by_horizon": supply_backtests[
            "metrics_by_horizon"
        ],
        "demand_metrics_by_region": demand_backtests[
            "metrics_by_region"
        ],
        "supply_metrics_by_region": supply_backtests[
            "metrics_by_region"
        ],
        "demand_win_rate": demand_backtests["win_rate"],
        "supply_win_rate": supply_backtests["win_rate"],
        "demand_win_rate_by_horizon": demand_backtests["win_rate_by_horizon"],
        "supply_win_rate_by_horizon": supply_backtests["win_rate_by_horizon"],
        "demand_win_rate_by_regime": demand_backtests["win_rate_by_regime"],
        "supply_win_rate_by_regime": supply_backtests["win_rate_by_regime"],
        "model_summary": model_summary,
        "demand_forecast": demand_forecast,
        "supply_forecast": supply_forecast,
        "supply_calibration": supply_calibration,
        "demand_history_summary": demand_history,
        "supply_history_summary": supply_history,
        "accounting": accounting,
        "combined": combined,
        "checks": checks,
        "input_hashes": _input_hashes(root, resolved_config_path),
    }
    for key, frame in frames.items():
        write_csv_deterministic(frame, paths[key])

    deterministic_hashes = {
        key: sha256_file(paths[key])
        for key in frames
    }
    summary = {
        "pipeline_id": "ecadin_production_forecasting_v1",
        "schema_version": config.schema_version,
        "status": "completed",
        "generated_at_utc": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
        "project_root": relative_posix_path(root, root),
        "demand_panel_contract": demand_panel_contract,
        "supply_panel_contract": supply_panel_contract,
        "demand_backtest_rows": len(
            demand_backtests["predictions"]
        ),
        "supply_backtest_rows": len(
            supply_backtests["predictions"]
        ),
        "demand_forecast_rows": len(demand_forecast),
        "supply_forecast_rows": len(supply_forecast),
        "accounting_rows": len(accounting),
        "combined_rows": len(combined),
        "historical_incomplete_differences": int(
            (
                combined["data_type"].eq("historical")
                & ~combined["difference_available"]
            ).sum()
        ),
        "forecast_incomplete_differences": int(
            (
                combined["data_type"].eq("forecast")
                & ~combined["difference_available"]
            ).sum()
        ),
        "production_contracts_passed": int(checks["passed"].sum()),
        "production_contracts_total": len(checks),
        "canonical_master_modified": False,
        "silent_imputation": False,
        "ruptl_adjustment_applied": False,
        "accounting_disclaimer": config.accounting_disclaimer,
        "deterministic_output_hashes": deterministic_hashes,
        "output_files": {
            key: relative_posix_path(path, root)
            for key, path in paths.items()
        },
    }
    write_json(summary, paths["summary"])
    return {
        "config": config,
        "frames": frames,
        "paths": paths,
        "summary": summary,
    }
