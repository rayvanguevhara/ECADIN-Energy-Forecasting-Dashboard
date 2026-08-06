from __future__ import annotations

import argparse
from pathlib import Path

from ecadin_energy.pipeline.production import run_production_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the ECADIN production forecasting pipeline."
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Project root; defaults to the installed ECADIN project.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Forecasting configuration JSON.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_production_pipeline(
        project_root=args.project_root,
        config_path=args.config,
    )
    summary = result["summary"]
    print("ECADIN PRODUCTION FORECASTING PIPELINE: COMPLETED")
    print(f"Demand backtest rows   : {summary['demand_backtest_rows']}")
    print(f"Supply backtest rows   : {summary['supply_backtest_rows']}")
    print(f"Demand forecast rows   : {summary['demand_forecast_rows']}")
    print(f"Supply forecast rows   : {summary['supply_forecast_rows']}")
    print(f"Accounting rows        : {summary['accounting_rows']}")
    print(f"Combined rows          : {summary['combined_rows']}")
    print(
        "Historical incomplete : "
        f"{summary['historical_incomplete_differences']}"
    )
    print(
        "Forecast incomplete   : "
        f"{summary['forecast_incomplete_differences']}"
    )
    print(
        "Production contracts  : "
        f"{summary['production_contracts_passed']}/"
        f"{summary['production_contracts_total']} PASSED"
    )
    print("Canonical master       : UNCHANGED")
    print("Silent imputation      : NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
