from __future__ import annotations

from pathlib import Path
from typing import Any

from ecadin_energy.dashboard.frontend_refresh import refresh_frontend_data
from ecadin_energy.dashboard.promotion import promote_dashboard_staging
from ecadin_energy.dashboard.staging import build_dashboard_staging
from ecadin_energy.dashboard.validation import validate_dashboard_production, validate_dashboard_staging


def run_dashboard_pipeline(
    *,
    project_root: str | Path | None = None,
    config_path: str | Path | None = None,
    refresh_frontend: bool = True,
    run_frontend_build: bool = False,
) -> dict[str, Any]:
    staging = build_dashboard_staging(project_root=project_root, config_path=config_path)
    staging_checks = validate_dashboard_staging(project_root=project_root, config_path=config_path)
    promotion = promote_dashboard_staging(project_root=project_root, config_path=config_path)
    production_checks = validate_dashboard_production(project_root=project_root, config_path=config_path)
    frontend = None
    if refresh_frontend:
        frontend = refresh_frontend_data(
            project_root=project_root,
            config_path=config_path,
            run_build=run_frontend_build,
        )
    return {
        "staging": staging["summary"],
        "staging_checks": staging_checks,
        "promotion": promotion,
        "production_checks": production_checks,
        "frontend": frontend,
    }
