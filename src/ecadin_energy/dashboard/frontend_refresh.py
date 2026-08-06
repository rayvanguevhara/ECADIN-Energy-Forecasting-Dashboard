from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pandas as pd

from ecadin_energy.dashboard.configuration import load_dashboard_config
from ecadin_energy.dashboard.contracts import DashboardContractError
from ecadin_energy.dashboard.serializers import atomic_copy, sha256_file, write_csv, write_json
from ecadin_energy.dashboard.validation import validate_dashboard_directory


def snapshot_frontend(frontend: Path, excluded_directories: tuple[str, ...], allowed_mutations: tuple[str, ...]) -> dict[str, str]:
    excluded = set(excluded_directories)
    allowed = {Path(value).as_posix() for value in allowed_mutations}
    snapshot: dict[str, str] = {}
    if not frontend.is_dir():
        return snapshot
    for path in sorted(frontend.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(frontend)
        if any(part in excluded for part in relative.parts):
            continue
        if relative.as_posix() in allowed:
            continue
        snapshot[relative.as_posix()] = sha256_file(path)
    return snapshot


def refresh_frontend_data(
    *,
    project_root: str | Path | None = None,
    config_path: str | Path | None = None,
    run_build: bool = False,
) -> dict[str, Any]:
    config = load_dashboard_config(config_path, project_root=project_root)
    paths = config.paths(project_root)
    validate_dashboard_directory(paths.production, project_root=paths.root, config_path=config_path)
    if not (paths.frontend / "package.json").is_file():
        raise FileNotFoundError(f"Frontend source is not installed: {paths.frontend}")
    if not paths.frontend_geojson.is_file():
        raise FileNotFoundError(f"Frontend GeoJSON is missing: {paths.frontend_geojson}")

    before = snapshot_frontend(
        paths.frontend,
        config.excluded_frontend_snapshot_directories,
        config.allowed_frontend_mutations,
    )
    source = paths.production / "dashboard-production.json"
    atomic_copy(source, paths.frontend_dataset)
    after = snapshot_frontend(
        paths.frontend,
        config.excluded_frontend_snapshot_directories,
        config.allowed_frontend_mutations,
    )
    changed = sorted(set(before) | set(after))
    changed = [key for key in changed if before.get(key) != after.get(key)]
    if changed:
        raise DashboardContractError(
            "Frontend refresh modified forbidden source files: " + ", ".join(changed)
        )

    payload = json.loads(paths.frontend_dataset.read_text(encoding="utf-8"))
    rows = [
        {
            "check_id": "frontend_dataset_hash",
            "passed": sha256_file(source) == sha256_file(paths.frontend_dataset),
            "observed": sha256_file(paths.frontend_dataset),
            "expected": sha256_file(source),
        },
        {
            "check_id": "frontend_nondata_source_unchanged",
            "passed": not changed,
            "observed": changed,
            "expected": [],
        },
        {
            "check_id": "frontend_payload_contract",
            "passed": payload.get("row_count") == 680 and payload.get("region_count") == 34,
            "observed": [payload.get("row_count"), payload.get("region_count")],
            "expected": [680, 34],
        },
    ]

    build_result: dict[str, Any] | None = None
    if run_build:
        npm = shutil.which("npm.cmd" if os.name == "nt" else "npm") or shutil.which("npm")
        if npm is None:
            raise FileNotFoundError("npm executable was not found")
        completed = subprocess.run(
            [npm, "run", "build"], cwd=paths.frontend, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
        )
        build_result = {
            "return_code": completed.returncode,
            "output_tail": completed.stdout[-8000:],
        }
        rows.append({
            "check_id": "frontend_production_build",
            "passed": completed.returncode == 0,
            "observed": completed.returncode,
            "expected": 0,
        })
        if completed.returncode != 0:
            raise DashboardContractError("Frontend production build failed:\n" + completed.stdout[-8000:])

    checks = pd.DataFrame(rows)
    paths.reports.mkdir(parents=True, exist_ok=True)
    write_csv(checks, paths.reports / "frontend_refresh_checks.csv")
    summary = {
        "status": "refreshed",
        "frontend_dataset": paths.frontend_dataset.relative_to(paths.root).as_posix(),
        "frontend_dataset_sha256": sha256_file(paths.frontend_dataset),
        "nondata_files_checked": len(before),
        "nondata_files_changed": changed,
        "build": build_result,
    }
    write_json(summary, paths.reports / "frontend_refresh_summary.json")
    return summary
