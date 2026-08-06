from __future__ import annotations

import argparse
from pathlib import Path

from ecadin_energy.dashboard.frontend_refresh import refresh_frontend_data
from ecadin_energy.dashboard.validation import validate_dashboard_production
from ecadin_energy.pipeline.dashboard import run_dashboard_pipeline
from ecadin_energy.pipeline.production import run_production_pipeline
from ecadin_energy.pipeline.validation import validate_production_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ecadin", description="ECADIN clean-project command line interface.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status", help="Show clean-project component status.")

    forecast = subparsers.add_parser("forecast", help="Build or validate production forecasting outputs.")
    forecast_sub = forecast.add_subparsers(dest="forecast_command", required=True)
    for command, help_text in (("build", "Run production forecasting."), ("validate", "Validate forecasting outputs.")):
        child = forecast_sub.add_parser(command, help=help_text)
        child.add_argument("--project-root", type=Path, default=None)
        child.add_argument("--config", type=Path, default=None)

    dashboard = subparsers.add_parser("dashboard", help="Build, refresh, or validate dashboard production data.")
    dashboard_sub = dashboard.add_subparsers(dest="dashboard_command", required=True)
    build = dashboard_sub.add_parser("build", help="Run dashboard staging, promotion, and frontend refresh.")
    build.add_argument("--project-root", type=Path, default=None)
    build.add_argument("--config", type=Path, default=None)
    build.add_argument("--skip-frontend-refresh", action="store_true")
    build.add_argument("--run-frontend-build", action="store_true")
    validate = dashboard_sub.add_parser("validate", help="Validate dashboard production outputs.")
    validate.add_argument("--project-root", type=Path, default=None)
    validate.add_argument("--config", type=Path, default=None)
    refresh = dashboard_sub.add_parser("refresh", help="Refresh only dashboard-production.json.")
    refresh.add_argument("--project-root", type=Path, default=None)
    refresh.add_argument("--config", type=Path, default=None)
    refresh.add_argument("--run-frontend-build", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "status":
        root = Path(__file__).resolve().parents[2]
        print("ECADIN clean project initialized")
        print(f"Project root  : {root}")
        print("Forecast core : " + ("installed" if (root / "configs/forecasting/production.json").is_file() else "not installed"))
        print("Forecast data : " + ("built" if (root / "outputs/production").is_dir() else "not built"))
        print("Dashboard core: " + ("installed" if (root / "configs/dashboard/production.json").is_file() else "not installed"))
        print("Dashboard data: " + ("built" if (root / "outputs/dashboard/production/dashboard-production.json").is_file() else "not built"))
        print("Frontend      : " + ("installed" if (root / "frontend-dashboard/package.json").is_file() else "not installed"))
        print("Legacy root   : D:\\ECADIN Project (read-only)")
        return 0

    if args.command == "forecast":
        if args.forecast_command == "build":
            result = run_production_pipeline(project_root=args.project_root, config_path=args.config)
            summary = result["summary"]
            print("ECADIN PRODUCTION FORECASTING PIPELINE: COMPLETED")
            print(f"Contracts     : {summary['production_contracts_passed']}/{summary['production_contracts_total']} PASSED")
            print(f"Combined rows : {summary['combined_rows']}")
            return 0
        checks = validate_production_pipeline(project_root=args.project_root, config_path=args.config)
        print("ECADIN PRODUCTION FORECASTING VALIDATION: PASSED")
        print(checks.to_string(index=False))
        return 0

    if args.command == "dashboard":
        if args.dashboard_command == "build":
            result = run_dashboard_pipeline(
                project_root=args.project_root,
                config_path=args.config,
                refresh_frontend=not args.skip_frontend_refresh,
                run_frontend_build=args.run_frontend_build,
            )
            checks = result["production_checks"]
            print("ECADIN DASHBOARD PRODUCTION PIPELINE: COMPLETED")
            print(f"Region-year rows      : {result['staging']['region_rows']}")
            print(f"Production contracts : {int(checks['passed'].sum())}/{len(checks)} PASSED")
            print("Frontend refresh      : " + ("COMPLETED" if result["frontend"] else "SKIPPED"))
            return 0
        if args.dashboard_command == "validate":
            checks = validate_dashboard_production(project_root=args.project_root, config_path=args.config)
            print("ECADIN DASHBOARD VALIDATION: PASSED")
            print(checks.to_string(index=False))
            return 0
        result = refresh_frontend_data(
            project_root=args.project_root,
            config_path=args.config,
            run_build=args.run_frontend_build,
        )
        print("ECADIN FRONTEND DATA REFRESH: COMPLETED")
        print(f"Dataset SHA256 : {result['frontend_dataset_sha256']}")
        print("TSX/CSS source : UNCHANGED")
        return 0

    parser.error("Unsupported command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
