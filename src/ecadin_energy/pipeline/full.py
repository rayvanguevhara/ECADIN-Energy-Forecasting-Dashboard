from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

from ecadin_energy.config import PATHS
from ecadin_energy.dashboard.validation import validate_dashboard_production
from ecadin_energy.forecasting.production.artifacts import relative_posix_path, write_json
from ecadin_energy.pipeline.dashboard import run_dashboard_pipeline
from ecadin_energy.pipeline.data import run_data_pipeline, validate_data_pipeline
from ecadin_energy.pipeline.production import run_production_pipeline
from ecadin_energy.pipeline.release import run_frontend_build, validate_frontend_release
from ecadin_energy.pipeline.validation import validate_production_pipeline


STAGE_ORDER = ("data", "forecast", "dashboard", "frontend")


def _root(project_root: str | Path | None) -> Path:
    return Path(project_root).resolve() if project_root else PATHS.root


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _execute_stage(
    name: str,
    function: Callable[[], Any],
    records: list[dict[str, Any]],
) -> Any:
    started = _utc_now()
    clock = perf_counter()
    try:
        result = function()
    except Exception as exc:
        records.append(
            {
                "stage": name,
                "status": "failed",
                "started_at_utc": started,
                "finished_at_utc": _utc_now(),
                "duration_seconds": round(perf_counter() - clock, 3),
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        )
        raise
    records.append(
        {
            "stage": name,
            "status": "passed",
            "started_at_utc": started,
            "finished_at_utc": _utc_now(),
            "duration_seconds": round(perf_counter() - clock, 3),
        }
    )
    return result


def validate_all(
    *,
    project_root: str | Path | None = None,
    forecast_config_path: str | Path | None = None,
    dashboard_config_path: str | Path | None = None,
) -> dict[str, Any]:
    root = _root(project_root)
    data_checks = validate_data_pipeline(project_root=root)
    forecast_checks = validate_production_pipeline(
        project_root=root,
        config_path=forecast_config_path,
    )
    dashboard_checks = validate_dashboard_production(
        project_root=root,
        config_path=dashboard_config_path,
    )
    frontend_checks = validate_frontend_release(
        project_root=root,
        config_path=dashboard_config_path,
    )
    return {
        "data": data_checks,
        "forecast": forecast_checks,
        "dashboard": dashboard_checks,
        "frontend": frontend_checks,
        "checks_passed": int(
            data_checks["passed"].sum()
            + forecast_checks["passed"].sum()
            + dashboard_checks["passed"].sum()
            + frontend_checks["passed"].sum()
        ),
        "checks_total": int(
            len(data_checks)
            + len(forecast_checks)
            + len(dashboard_checks)
            + len(frontend_checks)
        ),
    }


def run_full_pipeline(
    *,
    project_root: str | Path | None = None,
    forecast_config_path: str | Path | None = None,
    dashboard_config_path: str | Path | None = None,
    start_at: str = "data",
    run_frontend_production_build: bool = False,
    frontend_build_target: str = "vercel",
) -> dict[str, Any]:
    root = _root(project_root)
    if start_at not in STAGE_ORDER:
        raise ValueError(f"start_at must be one of: {', '.join(STAGE_ORDER)}")

    summary_path = root / "outputs/reports/release/full_pipeline_latest.json"
    records: list[dict[str, Any]] = []
    summary: dict[str, Any] = {
        "schema_version": "ecadin_full_pipeline_v1",
        "status": "running",
        "started_at_utc": _utc_now(),
        "project_root": relative_posix_path(root, root),
        "start_at": start_at,
        "frontend_build_requested": run_frontend_production_build,
        "frontend_build_target": frontend_build_target,
        "legacy_project_modified": False,
        "stages": records,
    }

    start_index = STAGE_ORDER.index(start_at)
    try:
        if start_index <= STAGE_ORDER.index("data"):
            _execute_stage(
                "data_build_and_validation",
                lambda: run_data_pipeline(project_root=root),
                records,
            )

        if start_index <= STAGE_ORDER.index("forecast"):
            _execute_stage(
                "forecast_build",
                lambda: run_production_pipeline(
                    project_root=root,
                    config_path=forecast_config_path,
                ),
                records,
            )
            _execute_stage(
                "forecast_validation",
                lambda: validate_production_pipeline(
                    project_root=root,
                    config_path=forecast_config_path,
                ),
                records,
            )

        if start_index <= STAGE_ORDER.index("dashboard"):
            _execute_stage(
                "dashboard_build_refresh",
                lambda: run_dashboard_pipeline(
                    project_root=root,
                    config_path=dashboard_config_path,
                    refresh_frontend=True,
                    run_frontend_build=False,
                ),
                records,
            )
            _execute_stage(
                "dashboard_validation",
                lambda: validate_dashboard_production(
                    project_root=root,
                    config_path=dashboard_config_path,
                ),
                records,
            )
            _execute_stage(
                "frontend_release_validation",
                lambda: validate_frontend_release(
                    project_root=root,
                    config_path=dashboard_config_path,
                ),
                records,
            )

        if start_index == STAGE_ORDER.index("frontend"):
            _execute_stage(
                "frontend_release_validation",
                lambda: validate_frontend_release(
                    project_root=root,
                    config_path=dashboard_config_path,
                ),
                records,
            )

        if run_frontend_production_build:
            _execute_stage(
                "frontend_production_build",
                lambda: run_frontend_build(
                    project_root=root,
                    target=frontend_build_target,
                ),
                records,
            )

        summary["status"] = "completed"
        summary["finished_at_utc"] = _utc_now()
        summary["stages_passed"] = sum(
            record["status"] == "passed" for record in records
        )
        summary["stages_total"] = len(records)
        write_json(summary, summary_path)
        return summary
    except Exception:
        summary["status"] = "failed"
        summary["finished_at_utc"] = _utc_now()
        summary["stages_passed"] = sum(
            record["status"] == "passed" for record in records
        )
        summary["stages_total"] = len(records)
        write_json(summary, summary_path)
        raise
