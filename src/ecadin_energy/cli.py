from __future__ import annotations

import argparse
from pathlib import Path

from ecadin_energy.dashboard.frontend_refresh import refresh_frontend_data
from ecadin_energy.dashboard.validation import validate_dashboard_production
from ecadin_energy.pipeline.dashboard import run_dashboard_pipeline
from ecadin_energy.pipeline.data import run_data_pipeline, validate_data_pipeline
from ecadin_energy.pipeline.full import run_full_pipeline, validate_all
from ecadin_energy.pipeline.production import run_production_pipeline
from ecadin_energy.pipeline.release import run_frontend_build, validate_frontend_release
from ecadin_energy.pipeline.validation import validate_production_pipeline


def _add_project_root(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project-root", type=Path, default=None)


def _add_config(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", type=Path, default=None)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ecadin",
        description="ECADIN clean-project command line interface.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status", help="Show clean-project component status.")

    data = subparsers.add_parser(
        "data",
        help="Build or validate processed data and canonical masters.",
    )
    data_sub = data.add_subparsers(dest="data_command", required=True)
    data_build = data_sub.add_parser("build", help="Run all data cleaners and canonical mastering.")
    _add_project_root(data_build)
    data_validate = data_sub.add_parser("validate", help="Validate reference, processed, and canonical data.")
    _add_project_root(data_validate)

    forecast = subparsers.add_parser(
        "forecast",
        help="Build or validate production forecasting outputs.",
    )
    forecast_sub = forecast.add_subparsers(dest="forecast_command", required=True)
    for command, help_text in (
        ("build", "Run production forecasting."),
        ("validate", "Validate forecasting outputs."),
    ):
        child = forecast_sub.add_parser(command, help=help_text)
        _add_project_root(child)
        _add_config(child)

    dashboard = subparsers.add_parser(
        "dashboard",
        help="Build, refresh, or validate dashboard production data.",
    )
    dashboard_sub = dashboard.add_subparsers(dest="dashboard_command", required=True)
    dashboard_build = dashboard_sub.add_parser(
        "build",
        help="Run dashboard staging, promotion, and frontend refresh.",
    )
    _add_project_root(dashboard_build)
    _add_config(dashboard_build)
    dashboard_build.add_argument("--skip-frontend-refresh", action="store_true")
    dashboard_build.add_argument("--run-frontend-build", action="store_true")

    dashboard_validate = dashboard_sub.add_parser(
        "validate",
        help="Validate dashboard production outputs.",
    )
    _add_project_root(dashboard_validate)
    _add_config(dashboard_validate)

    dashboard_refresh = dashboard_sub.add_parser(
        "refresh",
        help="Refresh only dashboard-production.json.",
    )
    _add_project_root(dashboard_refresh)
    _add_config(dashboard_refresh)
    dashboard_refresh.add_argument("--run-frontend-build", action="store_true")

    frontend = subparsers.add_parser(
        "frontend",
        help="Validate or build the frontend release.",
    )
    frontend_sub = frontend.add_subparsers(dest="frontend_command", required=True)
    frontend_validate = frontend_sub.add_parser(
        "validate",
        help="Validate frontend dataset and Vercel contracts.",
    )
    _add_project_root(frontend_validate)
    _add_config(frontend_validate)
    frontend_build = frontend_sub.add_parser(
        "build",
        help="Run the production frontend build.",
    )
    _add_project_root(frontend_build)
    frontend_build.add_argument(
        "--target",
        choices=("vercel", "local"),
        default="vercel",
    )

    validate = subparsers.add_parser(
        "validate",
        help="Run consolidated validation.",
    )
    validate_sub = validate.add_subparsers(dest="validate_command", required=True)
    validate_all_parser = validate_sub.add_parser(
        "all",
        help="Validate data, forecast, dashboard, and frontend release.",
    )
    _add_project_root(validate_all_parser)
    validate_all_parser.add_argument("--forecast-config", type=Path, default=None)
    validate_all_parser.add_argument("--dashboard-config", type=Path, default=None)

    full = subparsers.add_parser(
        "full",
        help="Run the production pipeline end to end.",
    )
    _add_project_root(full)
    full.add_argument("--forecast-config", type=Path, default=None)
    full.add_argument("--dashboard-config", type=Path, default=None)
    full.add_argument(
        "--start-at",
        choices=("data", "forecast", "dashboard", "frontend"),
        default="data",
        help="Resume from a validated stage without rebuilding earlier stages.",
    )
    full.add_argument("--run-frontend-build", action="store_true")
    full.add_argument(
        "--frontend-build-target",
        choices=("vercel", "local"),
        default="vercel",
    )
    return parser


def _status(root: Path) -> int:
    raw_directories = (
        "distributed_electricity",
        "local_generation",
        "installed_capacity",
        "electricity_sold",
        "electricity_customers",
    )
    raw_ready = all(
        any((root / "data/raw/bps" / directory).glob("*.csv"))
        for directory in raw_directories
    )
    print("ECADIN clean project initialized")
    print(f"Project root   : {root}")
    print("Raw data       : " + ("available" if raw_ready else "not available"))
    print(
        "Reference layer: "
        + ("installed" if (root / "data/reference/reference_layer_contract.json").is_file() else "not installed")
    )
    print(
        "Canonical data : "
        + ("built" if (root / "data/processed/master/regional_energy_master.csv").is_file() else "not built")
    )
    print(
        "Forecast core  : "
        + ("installed" if (root / "configs/forecasting/production.json").is_file() else "not installed")
    )
    print(
        "Forecast data  : "
        + ("built" if (root / "outputs/production/reports/production_run_summary.json").is_file() else "not built")
    )
    print(
        "Dashboard core : "
        + ("installed" if (root / "configs/dashboard/production.json").is_file() else "not installed")
    )
    print(
        "Dashboard data : "
        + ("built" if (root / "outputs/dashboard/production/dashboard-production.json").is_file() else "not built")
    )
    print(
        "Frontend       : "
        + ("installed" if (root / "frontend-dashboard/package.json").is_file() else "not installed")
    )
    print(
        "Vercel target  : "
        + ("configured" if (root / "frontend-dashboard/vercel.json").is_file() else "not configured")
    )
    print("Legacy root    : D:\\ECADIN Project (read-only)")
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    default_root = Path(__file__).resolve().parents[2]

    if args.command == "status":
        return _status(default_root)

    if args.command == "data":
        if args.data_command == "build":
            summary = run_data_pipeline(project_root=args.project_root)
            print("ECADIN DATA PIPELINE: COMPLETED")
            print(f"Validation checks : {summary['checks_passed']}/{summary['checks_total']} PASSED")
            print(f"Regional rows     : {summary['canonical_validation']['regional_rows']}")
            print(f"National rows     : {summary['canonical_validation']['national_rows']}")
            print("Silent imputation : NO")
            return 0
        checks = validate_data_pipeline(project_root=args.project_root)
        print("ECADIN DATA VALIDATION: PASSED")
        print(checks.to_string(index=False))
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
                f"Contracts     : {summary['production_contracts_passed']}/"
                f"{summary['production_contracts_total']} PASSED"
            )
            print(f"Combined rows : {summary['combined_rows']}")
            return 0
        checks = validate_production_pipeline(
            project_root=args.project_root,
            config_path=args.config,
        )
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
            print(
                f"Production contracts : {int(checks['passed'].sum())}/"
                f"{len(checks)} PASSED"
            )
            print(
                "Frontend refresh      : "
                + ("COMPLETED" if result["frontend"] else "SKIPPED")
            )
            return 0
        if args.dashboard_command == "validate":
            checks = validate_dashboard_production(
                project_root=args.project_root,
                config_path=args.config,
            )
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

    if args.command == "frontend":
        if args.frontend_command == "validate":
            checks = validate_frontend_release(
                project_root=args.project_root,
                config_path=args.config,
            )
            print("ECADIN FRONTEND RELEASE VALIDATION: PASSED")
            print(checks.to_string(index=False))
            return 0
        result = run_frontend_build(
            project_root=args.project_root,
            target=args.target,
        )
        print("ECADIN FRONTEND PRODUCTION BUILD: PASSED")
        print(f"Target      : {result['target']}")
        print(f"Return code : {result['return_code']}")
        return 0

    if args.command == "validate" and args.validate_command == "all":
        result = validate_all(
            project_root=args.project_root,
            forecast_config_path=args.forecast_config,
            dashboard_config_path=args.dashboard_config,
        )
        print("ECADIN CONSOLIDATED VALIDATION: PASSED")
        print(f"Checks : {result['checks_passed']}/{result['checks_total']} PASSED")
        return 0

    if args.command == "full":
        summary = run_full_pipeline(
            project_root=args.project_root,
            forecast_config_path=args.forecast_config,
            dashboard_config_path=args.dashboard_config,
            start_at=args.start_at,
            run_frontend_production_build=args.run_frontend_build,
            frontend_build_target=args.frontend_build_target,
        )
        print("ECADIN FULL PRODUCTION PIPELINE: COMPLETED")
        print(f"Stages : {summary['stages_passed']}/{summary['stages_total']} PASSED")
        print(f"Start  : {summary['start_at']}")
        print(
            "Frontend build : "
            + ("COMPLETED" if summary["frontend_build_requested"] else "SKIPPED")
        )
        return 0

    parser.error("Unsupported command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
