from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pandas as pd

from ecadin_energy.config import PATHS
from ecadin_energy.dashboard.configuration import load_dashboard_config
from ecadin_energy.dashboard.contracts import DashboardContractError
from ecadin_energy.dashboard.serializers import sha256_file, write_csv, write_json


def _root(project_root: str | Path | None) -> Path:
    return Path(project_root).resolve() if project_root else PATHS.root


def validate_frontend_release(
    *,
    project_root: str | Path | None = None,
    config_path: str | Path | None = None,
) -> pd.DataFrame:
    root = _root(project_root)
    config = load_dashboard_config(config_path, project_root=root)
    paths = config.paths(root)
    production = paths.production / "dashboard-production.json"
    frontend = paths.frontend_dataset
    vite_config = paths.frontend / "vite.config.ts"
    vercel_config = paths.frontend / "vercel.json"
    styles = paths.frontend / "src/styles.css"

    required = [production, frontend, vite_config, vercel_config, styles]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "Frontend release files are missing:\n- " + "\n- ".join(missing)
        )

    production_payload = json.loads(production.read_text(encoding="utf-8"))
    frontend_payload = json.loads(frontend.read_text(encoding="utf-8"))
    vercel_payload = json.loads(vercel_config.read_text(encoding="utf-8"))
    vite_text = vite_config.read_text(encoding="utf-8")

    rows = [
        {
            "check_id": "frontend_dataset_hash",
            "passed": sha256_file(production) == sha256_file(frontend),
            "observed": sha256_file(frontend),
            "expected": sha256_file(production),
            "details": "The frontend publishes the validated dashboard production payload.",
        },
        {
            "check_id": "frontend_payload_schema",
            "passed": (
                frontend_payload.get("schema_version")
                == config.frontend_schema_version
                and frontend_payload.get("row_count") == 680
                and frontend_payload.get("region_count") == 34
            ),
            "observed": [
                frontend_payload.get("schema_version"),
                frontend_payload.get("row_count"),
                frontend_payload.get("region_count"),
            ],
            "expected": [config.frontend_schema_version, 680, 34],
            "details": "Frontend payload schema, rows, and regions are stable.",
        },
        {
            "check_id": "production_payload_schema",
            "passed": production_payload.get("schema_version") == config.frontend_schema_version,
            "observed": production_payload.get("schema_version"),
            "expected": config.frontend_schema_version,
            "details": "Dashboard production uses the frontend contract version.",
        },
        {
            "check_id": "vercel_framework_contract",
            "passed": vercel_payload.get("framework") == "tanstack-start",
            "observed": vercel_payload.get("framework"),
            "expected": "tanstack-start",
            "details": "Vercel is configured for TanStack Start.",
        },
        {
            "check_id": "vercel_nitro_target_contract",
            "passed": (
                'isVercelBuild ? "vercel" : "node-server"' in vite_text
                and 'process.env.VERCEL === "1"' in vite_text
            ),
            "observed": "vercel conditional present" if "vercel" in vite_text else "missing",
            "expected": "VERCEL=1 selects Nitro vercel; local selects node-server",
            "details": "The production hosting target is selected without changing frontend source.",
        },
    ]
    frame = pd.DataFrame(rows)
    failures = frame.loc[~frame["passed"]]
    if not failures.empty:
        raise DashboardContractError(
            "Frontend release validation failed:\n" + failures.to_string(index=False)
        )
    paths.reports.mkdir(parents=True, exist_ok=True)
    write_csv(frame, paths.reports / "frontend_release_checks.csv")
    return frame


def run_frontend_build(
    *,
    project_root: str | Path | None = None,
    target: str = "vercel",
) -> dict[str, Any]:
    root = _root(project_root)
    frontend = root / "frontend-dashboard"
    if target not in {"vercel", "local"}:
        raise ValueError("Frontend build target must be 'vercel' or 'local'.")
    if not (frontend / "package.json").is_file():
        raise FileNotFoundError(f"Frontend source is not installed: {frontend}")

    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm") or shutil.which("npm")
    if npm is None:
        raise FileNotFoundError("npm executable was not found")

    environment = os.environ.copy()
    if target == "vercel":
        environment["VERCEL"] = "1"
    else:
        environment.pop("VERCEL", None)

    completed = subprocess.run(
        [npm, "run", "build"],
        cwd=frontend,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    output_tail = completed.stdout[-12000:]
    result = {
        "target": target,
        "return_code": completed.returncode,
        "passed": completed.returncode == 0,
        "output_tail": output_tail,
    }
    if completed.returncode != 0:
        raise DashboardContractError(
            f"Frontend {target} build failed:\n{output_tail}"
        )
    report = root / "outputs/dashboard/reports/frontend_build_summary.json"
    write_json(result, report)
    return result
