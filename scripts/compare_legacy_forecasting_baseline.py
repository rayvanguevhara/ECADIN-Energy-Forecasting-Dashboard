from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def _load(path: Path) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(path)
    return pd.read_csv(path, low_memory=False)


def _compare(
    *,
    check_id: str,
    new: pd.DataFrame,
    legacy: pd.DataFrame,
    new_keys: list[str],
    legacy_keys: list[str],
    new_value: str,
    legacy_value: str,
    tolerance: float = 1e-8,
) -> dict[str, object]:
    left = new[new_keys + [new_value]].rename(
        columns={
            **dict(zip(new_keys, legacy_keys)),
            new_value: "new_value",
        }
    )
    right = legacy[legacy_keys + [legacy_value]].rename(
        columns={legacy_value: "legacy_value"}
    )
    merged = left.merge(
        right,
        on=legacy_keys,
        how="outer",
        indicator=True,
        validate="one_to_one",
    )
    comparable = merged.loc[merged["_merge"].eq("both")].copy()
    comparable["absolute_difference"] = (
        comparable["new_value"] - comparable["legacy_value"]
    ).abs()
    max_difference = (
        float(comparable["absolute_difference"].max())
        if not comparable.empty
        else float("nan")
    )
    passed = (
        len(merged) == len(comparable)
        and max_difference <= tolerance
    )
    return {
        "check_id": check_id,
        "passed": passed,
        "new_rows": len(new),
        "legacy_rows": len(legacy),
        "matched_rows": len(comparable),
        "max_absolute_difference": max_difference,
        "tolerance": tolerance,
    }


def compare_baseline(
    project_root: Path,
    legacy_root: Path,
) -> pd.DataFrame:
    outputs = project_root / "outputs/production"
    legacy_outputs = legacy_root / "outputs"

    new_demand_forecast = _load(
        outputs / "forecasts/demand_forecast.csv"
    )
    old_demand_forecast = _load(
        legacy_outputs
        / "models/demand/demand_forecast_2025_2030.csv"
    )
    new_supply_forecast = _load(
        outputs / "forecasts/supply_forecast.csv"
    )
    old_supply_forecast = _load(
        legacy_outputs
        / "models/supply/supply_forecast_2025_2030.csv"
    )
    new_demand_backtest = _load(
        outputs / "backtests/demand_predictions.csv"
    )
    old_demand_backtest = _load(
        legacy_outputs
        / "models/demand/demand_baseline_all_predictions.csv"
    )
    new_supply_backtest = _load(
        outputs / "backtests/supply_predictions.csv"
    )
    old_supply_backtest = _load(
        legacy_outputs
        / "backtests/supply/phase3c_baselines_enriched_v1/"
        "supply_baseline_all_predictions.csv"
    )

    rows = [
        _compare(
            check_id="demand_point_forecast",
            new=new_demand_forecast,
            legacy=old_demand_forecast,
            new_keys=["region_name", "year"],
            legacy_keys=["provinsi", "tahun"],
            new_value="forecast_gwh",
            legacy_value="forecast_electricity_distributed_gwh",
        ),
        _compare(
            check_id="supply_point_forecast",
            new=new_supply_forecast,
            legacy=old_supply_forecast,
            new_keys=["region_name", "year"],
            legacy_keys=["provinsi", "tahun"],
            new_value="forecast_gwh",
            legacy_value="forecast_electricity_generated_gwh",
        ),
        _compare(
            check_id="supply_lower_80",
            new=new_supply_forecast,
            legacy=old_supply_forecast,
            new_keys=["region_name", "year"],
            legacy_keys=["provinsi", "tahun"],
            new_value="forecast_lower_80_gwh",
            legacy_value="forecast_lower_80_gwh",
        ),
        _compare(
            check_id="supply_upper_95",
            new=new_supply_forecast,
            legacy=old_supply_forecast,
            new_keys=["region_name", "year"],
            legacy_keys=["provinsi", "tahun"],
            new_value="forecast_upper_95_gwh",
            legacy_value="forecast_upper_95_gwh",
        ),
        _compare(
            check_id="demand_backtest_predictions",
            new=new_demand_backtest,
            legacy=old_demand_backtest,
            new_keys=[
                "protocol",
                "model",
                "region_name",
                "origin_year",
                "forecast_year",
                "horizon",
            ],
            legacy_keys=[
                "protocol",
                "model",
                "provinsi_model",
                "origin_year",
                "forecast_year",
                "horizon",
            ],
            new_value="prediction_gwh",
            legacy_value="prediction_gwh",
        ),
        _compare(
            check_id="supply_backtest_predictions",
            new=new_supply_backtest,
            legacy=old_supply_backtest,
            new_keys=[
                "protocol",
                "model",
                "region_name",
                "origin_year",
                "forecast_year",
                "horizon",
            ],
            legacy_keys=[
                "protocol",
                "model",
                "provinsi_model",
                "origin_year",
                "forecast_year",
                "horizon",
            ],
            new_value="prediction_gwh",
            legacy_value="prediction_gwh",
        ),
    ]
    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare clean forecasting outputs with legacy baseline."
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
    )
    parser.add_argument(
        "--legacy-root",
        type=Path,
        default=Path(r"D:\ECADIN Project"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
    )
    args = parser.parse_args()

    report = compare_baseline(
        args.project_root.resolve(),
        args.legacy_root.resolve(),
    )
    output = (
        args.output
        if args.output is not None
        else args.project_root
        / "outputs/production/reports/legacy_parity_report.csv"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(output, index=False, encoding="utf-8")
    print(report.to_string(index=False))
    if not report["passed"].all():
        raise SystemExit("Legacy forecasting parity failed")
    print(f"Legacy parity: {int(report['passed'].sum())}/{len(report)} PASSED")
    print(f"Report: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
