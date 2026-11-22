from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ecadin_energy.forecasting.configuration import ProductionConfig
from ecadin_energy.forecasting.exceptions import ContractError
from ecadin_energy.forecasting.production.artifacts import sha256_file


REQUIRED_WIN_RATE_OUTPUT_KEYS = (
    "demand_win_rate_by_horizon",
    "supply_win_rate_by_horizon",
    "demand_win_rate_by_regime",
    "supply_win_rate_by_regime",
)


def _check(
    rows: list[dict[str, object]],
    *,
    check_id: str,
    passed: bool,
    observed: object,
    expected: object,
    details: str,
) -> None:
    rows.append(
        {
            "check_id": check_id,
            "passed": bool(passed),
            "observed": str(observed),
            "expected": str(expected),
            "details": details,
        }
    )


def _to_bool_series(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False).astype(bool)
    return (
        series.astype("string")
        .str.strip()
        .str.lower()
        .eq("true")
        .fillna(False)
    )


def _expected_backtest_rows(
    panel: pd.DataFrame,
    config: ProductionConfig,
) -> int:
    """Compute expected backtest prediction count from panel eligibility and config."""
    eligible = panel.loc[
        _to_bool_series(panel["validation_eligible"])
        & panel["actual_gwh"].notna()
    ]
    one_step_rows = int(
        eligible["year"].isin(config.one_step_target_years).sum()
    )
    recursive_rows = sum(
        int(eligible["year"].eq(int(origin) + horizon).sum())
        for origin in config.recursive_origins
        for horizon in range(1, config.recursive_max_horizon + 1)
    )
    return len(config.baseline_models) * (one_step_rows + recursive_rows)


def _expected_historical_missing(
    demand_panel: pd.DataFrame,
    supply_panel: pd.DataFrame,
) -> int:
    """Count historical region-year pairs missing either demand or supply target."""
    merged = demand_panel[["region_id", "year", "training_gwh"]].merge(
        supply_panel[["region_id", "year", "training_gwh"]],
        on=["region_id", "year"],
        how="outer",
        suffixes=("_demand", "_supply"),
    )
    return int(
        (
            merged["training_gwh_demand"].isna()
            | merged["training_gwh_supply"].isna()
        ).sum()
    )


def _is_relative_posix_path(value: object) -> bool:
    """Validate that value is a non-empty normalized relative POSIX path."""
    if not isinstance(value, str) or not value:
        return False
    if "\\" in value or value.startswith("/"):
        return False
    if len(value) >= 2 and value[1] == ":":
        return False
    if Path(value).is_absolute():
        return False
    return ".." not in Path(value).parts


def _verify_input_hashes(root: Path) -> dict[str, object]:
    """Verify on-disk SHA-256 and byte sizes for production input artifacts."""
    hashes_path = (
        root / "outputs/production/reports/production_input_hashes.csv"
    )
    if not hashes_path.is_file():
        return {
            "check_id": "input_hashes_sha256",
            "passed": False,
            "observed": "missing production_input_hashes.csv",
            "expected": "all inputs verified",
            "details": f"Missing hash manifest: {hashes_path.name}",
        }

    manifest = pd.read_csv(hashes_path, low_memory=False)
    required_cols = {"input_id", "relative_path", "sha256", "size_bytes"}
    if not required_cols.issubset(manifest.columns) or manifest.empty:
        return {
            "check_id": "input_hashes_sha256",
            "passed": False,
            "observed": f"columns={list(manifest.columns)}, rows={len(manifest)}",
            "expected": f"non-empty with columns {sorted(required_cols)}",
            "details": "Invalid production_input_hashes.csv schema or empty manifest.",
        }

    errors: list[str] = []
    verified = 0
    total = int(len(manifest))
    for record in manifest.to_dict("records"):
        input_id = str(record["input_id"])
        rel_path = record["relative_path"]
        expected_sha = str(record["sha256"]).strip().upper()
        expected_size = int(record["size_bytes"])
        if not _is_relative_posix_path(rel_path):
            errors.append(f"{input_id}: non-relative path '{rel_path}'")
            continue
        target = root / str(rel_path)
        if not target.is_file():
            errors.append(f"{input_id}: missing file {rel_path}")
            continue
        actual_sha = sha256_file(target)
        actual_size = target.stat().st_size
        if actual_sha != expected_sha or actual_size != expected_size:
            errors.append(
                f"{input_id} ({rel_path}): expected sha256={expected_sha} "
                f"size={expected_size}, got sha256={actual_sha} "
                f"size={actual_size}"
            )
            continue
        verified += 1

    return {
        "check_id": "input_hashes_sha256",
        "passed": len(errors) == 0,
        "observed": f"verified={verified}/{total}",
        "expected": f"verified={total}/{total}",
        "details": (
            f"All {total} production input SHA-256 hashes verified."
            if not errors
            else "; ".join(errors)
        ),
    }


def _verify_output_hashes(root: Path) -> dict[str, object]:
    """Verify relative paths and on-disk SHA-256 hashes in run summary."""
    summary_path = (
        root / "outputs/production/reports/production_run_summary.json"
    )
    if not summary_path.is_file():
        return {
            "check_id": "output_hashes_sha256",
            "passed": False,
            "observed": "missing production_run_summary.json",
            "expected": "all outputs verified",
            "details": f"Missing run summary: {summary_path.name}",
        }

    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "check_id": "output_hashes_sha256",
            "passed": False,
            "observed": "invalid json",
            "expected": "valid production_run_summary.json",
            "details": f"Failed to parse run summary: {exc}",
        }

    errors: list[str] = []
    project_root_value = summary.get("project_root")
    if not _is_relative_posix_path(project_root_value):
        errors.append(
            f"project_root must be relative POSIX path, got '{project_root_value}'"
        )

    output_files = summary.get("output_files")
    output_hashes = summary.get("deterministic_output_hashes")
    if not isinstance(output_files, dict) or not output_files:
        errors.append("output_files missing or empty in summary")
        output_files = {}
    if not isinstance(output_hashes, dict) or not output_hashes:
        errors.append("deterministic_output_hashes missing or empty in summary")
        output_hashes = {}

    for key, rel_path in output_files.items():
        if not _is_relative_posix_path(rel_path):
            errors.append(f"output_files[{key}] non-relative path '{rel_path}'")

    for key in REQUIRED_WIN_RATE_OUTPUT_KEYS:
        if key not in output_files:
            errors.append(f"missing required output_files key '{key}'")
        if key not in output_hashes:
            errors.append(
                f"missing required deterministic_output_hashes key '{key}'"
            )

    missing_hashes = sorted(
        key
        for key in output_files
        if key != "summary" and key not in output_hashes
    )
    if missing_hashes:
        errors.append(
            "output_files missing hashes: " + ", ".join(missing_hashes)
        )

    if "summary" in output_files and _is_relative_posix_path(
        output_files["summary"]
    ):
        if not (root / str(output_files["summary"])).is_file():
            errors.append(f"summary file missing: {output_files['summary']}")

    verified = 0
    total = len(output_hashes)
    for key, expected_hash in output_hashes.items():
        rel_path = output_files.get(key)
        if not _is_relative_posix_path(rel_path):
            errors.append(f"{key}: invalid or missing output_files path")
            continue
        target = root / str(rel_path)
        if not target.is_file():
            errors.append(f"{key}: missing output file {rel_path}")
            continue
        actual_hash = sha256_file(target)
        expected_upper = str(expected_hash).strip().upper()
        if actual_hash != expected_upper:
            errors.append(
                f"{key} ({rel_path}): expected sha256={expected_upper}, "
                f"got sha256={actual_hash}"
            )
            continue
        verified += 1

    return {
        "check_id": "output_hashes_sha256",
        "passed": len(errors) == 0,
        "observed": f"verified={verified}/{total}",
        "expected": f"verified={total}/{total}",
        "details": (
            f"All {total} deterministic output SHA-256 hashes verified "
            f"with relative POSIX paths."
            if not errors
            else "; ".join(errors)
        ),
    }


def validate_production_frames(
    *,
    demand_panel: pd.DataFrame,
    supply_panel: pd.DataFrame,
    demand_backtest: pd.DataFrame,
    supply_backtest: pd.DataFrame,
    demand_forecast: pd.DataFrame,
    supply_forecast: pd.DataFrame,
    accounting: pd.DataFrame,
    combined: pd.DataFrame,
    config: ProductionConfig,
) -> pd.DataFrame:
    checks: list[dict[str, object]] = []
    expected_forecast_rows = (
        config.expected_regions * len(config.forecast_years)
    )
    expected_historical_rows = (
        config.expected_regions * len(config.historical_years)
    )
    demand_value_col = config.demand.output_value_column
    supply_value_col = config.supply.output_value_column

    panel_ok = (
        len(demand_panel) == expected_historical_rows
        and len(supply_panel) == expected_historical_rows
        and demand_panel["region_id"].nunique() == config.expected_regions
        and supply_panel["region_id"].nunique() == config.expected_regions
    )
    _check(
        checks,
        check_id="canonical_modeling_panels",
        passed=panel_ok,
        observed=f"{len(demand_panel)}/{len(supply_panel)}",
        expected=f"{expected_historical_rows}/{expected_historical_rows}",
        details=(
            f"Demand and supply panels use the same "
            f"{config.expected_regions}-region annual key grid."
        ),
    )

    expected_demand_predictions = _expected_backtest_rows(demand_panel, config)
    demand_backtest_ok = (
        len(demand_backtest) == expected_demand_predictions
        and not demand_backtest.duplicated(
            [
                "protocol",
                "model",
                "region_id",
                "origin_year",
                "forecast_year",
                "horizon",
            ]
        ).any()
    )
    _check(
        checks,
        check_id="demand_backtest_contract",
        passed=demand_backtest_ok,
        observed=len(demand_backtest),
        expected=expected_demand_predictions,
        details=(
            f"{len(config.baseline_models)} baselines; rolling "
            f"{min(config.one_step_target_years)}-{max(config.one_step_target_years)} "
            f"and recursive origins {min(config.recursive_origins)}-{max(config.recursive_origins)}."
        ),
    )

    expected_supply_predictions = _expected_backtest_rows(supply_panel, config)
    supply_backtest_ok = (
        len(supply_backtest) == expected_supply_predictions
        and not supply_backtest.duplicated(
            [
                "protocol",
                "model",
                "region_id",
                "origin_year",
                "forecast_year",
                "horizon",
            ]
        ).any()
    )
    _check(
        checks,
        check_id="supply_backtest_contract",
        passed=supply_backtest_ok,
        observed=len(supply_backtest),
        expected=expected_supply_predictions,
        details=(
            "Validation-eligible panel targets match configured backtest grid "
            "(missing targets excluded from evaluation rows)."
        ),
    )

    forecasts_ok = (
        len(demand_forecast) == expected_forecast_rows
        and len(supply_forecast) == expected_forecast_rows
        and demand_value_col in demand_forecast.columns
        and supply_value_col in supply_forecast.columns
        and demand_forecast[demand_value_col].notna().all()
        and supply_forecast[supply_value_col].notna().all()
        and demand_forecast[demand_value_col].ge(0).all()
        and supply_forecast[supply_value_col].ge(0).all()
    )
    _check(
        checks,
        check_id="production_forecasts",
        passed=forecasts_ok,
        observed=f"{len(demand_forecast)}/{len(supply_forecast)}",
        expected=f"{expected_forecast_rows}/{expected_forecast_rows}",
        details=(
            f"Demand {config.demand.model_label} and supply "
            f"{config.supply.model_label} forecasts for "
            f"{config.forecast_start_year}-{config.forecast_end_year}."
        ),
    )

    accounting_available = _to_bool_series(accounting["difference_available"])
    accounting_ok = (
        len(accounting) == expected_forecast_rows
        and accounting_available.all()
        and np.allclose(
            accounting["accounting_difference_gwh"],
            accounting["supply_gwh"] - accounting["demand_gwh"],
            rtol=0.0,
            atol=1e-9,
        )
    )
    _check(
        checks,
        check_id="accounting_difference",
        passed=accounting_ok,
        observed=len(accounting),
        expected=expected_forecast_rows,
        details=(
            "Accounting difference is local generation minus distributed "
            "electricity; it is not an adequacy indicator."
        ),
    )

    expected_combined_rows = (
        expected_historical_rows + expected_forecast_rows
    )
    expected_historical_missing = _expected_historical_missing(
        demand_panel,
        supply_panel,
    )
    diff_available = _to_bool_series(combined["difference_available"])
    historical_missing = int(
        (combined["data_type"].eq("historical") & ~diff_available).sum()
    )
    forecast_missing = int(
        (combined["data_type"].eq("forecast") & ~diff_available).sum()
    )
    combined_ok = (
        len(combined) == expected_combined_rows
        and historical_missing == expected_historical_missing
        and forecast_missing == 0
    )
    _check(
        checks,
        check_id="combined_history_forecast",
        passed=combined_ok,
        observed=(
            f"rows={len(combined)}, historical_missing="
            f"{historical_missing}, forecast_missing={forecast_missing}"
        ),
        expected=(
            f"rows={expected_combined_rows}, "
            f"historical_missing={expected_historical_missing}, "
            "forecast_missing=0"
        ),
        details=(
            f"{expected_historical_rows} historical rows plus "
            f"{expected_forecast_rows} forecast rows."
        ),
    )

    result = pd.DataFrame(checks)
    if not result["passed"].all():
        failed = result.loc[~result["passed"]]
        raise ContractError(
            "Production forecasting contracts failed:\n"
            + failed.to_string(index=False)
        )
    return result


def validate_written_outputs(
    *,
    project_root: str | Path,
    config: ProductionConfig,
    verify_hashes: bool = True,
) -> pd.DataFrame:
    root = Path(project_root).resolve()
    paths = {
        "demand_panel": root
        / "data/processed/modeling/demand_modeling_panel.csv",
        "supply_panel": root
        / "data/processed/modeling/supply_modeling_panel.csv",
        "demand_backtest": root
        / "outputs/production/backtests/demand_predictions.csv",
        "supply_backtest": root
        / "outputs/production/backtests/supply_predictions.csv",
        "demand_forecast": root
        / "outputs/production/forecasts/demand_forecast.csv",
        "supply_forecast": root
        / "outputs/production/forecasts/supply_forecast.csv",
        "accounting": root
        / "outputs/production/accounting/accounting_difference.csv",
        "combined": root
        / "outputs/production/combined/regional_energy_history_forecast.csv",
    }
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "Production forecasting outputs are missing: " + ", ".join(missing)
        )
    frames = {
        name: pd.read_csv(path, low_memory=False)
        for name, path in paths.items()
    }
    frame_checks = validate_production_frames(
        demand_panel=frames["demand_panel"],
        supply_panel=frames["supply_panel"],
        demand_backtest=frames["demand_backtest"],
        supply_backtest=frames["supply_backtest"],
        demand_forecast=frames["demand_forecast"],
        supply_forecast=frames["supply_forecast"],
        accounting=frames["accounting"],
        combined=frames["combined"],
        config=config,
    )
    if not verify_hashes:
        return frame_checks

    hash_checks = pd.DataFrame(
        [
            _verify_input_hashes(root),
            _verify_output_hashes(root),
        ]
    )
    all_checks = pd.concat([frame_checks, hash_checks], ignore_index=True)
    if not hash_checks["passed"].all():
        failed = hash_checks.loc[~hash_checks["passed"]]
        details = "; ".join(str(value) for value in failed["details"].tolist())
        raise ContractError(
            f"Production artifact hash verification failed: {details}\n"
            + failed.to_string(index=False)
        )
    return all_checks
