from __future__ import annotations

import argparse
from pathlib import Path

from ecadin_energy.pipeline.production import run_production_pipeline
from ecadin_energy.pipeline.validation import validate_production_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ecadin",
        description="ECADIN clean-project command line interface.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "status",
        help="Show clean-project and forecasting-core status.",
    )

    forecast = subparsers.add_parser(
        "forecast",
        help="Build or validate production forecasting outputs.",
    )
    forecast_sub = forecast.add_subparsers(
        dest="forecast_command",
        required=True,
    )
    build = forecast_sub.add_parser(
        "build",
        help="Run the full production forecasting pipeline.",
    )
    build.add_argument("--project-root", type=Path, default=None)
    build.add_argument("--config", type=Path, default=None)

    validate = forecast_sub.add_parser(
        "validate",
        help="Validate existing production forecasting outputs.",
    )
    validate.add_argument("--project-root", type=Path, default=None)
    validate.add_argument("--config", type=Path, default=None)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "status":
        root = Path(__file__).resolve().parents[2]
        config = root / "configs/forecasting/production.json"
        production = root / "outputs/production"
        print("ECADIN clean project initialized")
        print(f"Project root : {root}")
        print(
            "Forecast core: "
            + ("installed" if config.is_file() else "not installed")
        )
        print(
            "Production    : "
            + ("built" if production.is_dir() else "not built")
        )
        print("Legacy root  : D:\\ECADIN Project (read-only)")
        return 0

    if args.command == "forecast":
        if args.forecast_command == "build":
            result = run_production_pipeline(
                project_root=args.project_root,
                config_path=args.config,
            )
            summary = result["summary"]
            print("ECADIN PRODUCTION FORECASTING PIPELINE: COMPLETED")
            print(
                "Contracts     : "
                f"{summary['production_contracts_passed']}/"
                f"{summary['production_contracts_total']} PASSED"
            )
            print(
                f"Combined rows : {summary['combined_rows']}"
            )
            return 0

        if args.forecast_command == "validate":
            checks = validate_production_pipeline(
                project_root=args.project_root,
                config_path=args.config,
            )
            print("ECADIN PRODUCTION FORECASTING VALIDATION: PASSED")
            print(checks.to_string(index=False))
            return 0

    parser.error("Unsupported command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
