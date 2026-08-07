from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from ecadin_energy.dashboard.configuration import load_dashboard_config
from ecadin_energy.dashboard.serializers import atomic_copy, sha256_file, write_json
from ecadin_energy.dashboard.staging import DETERMINISTIC_FILES
from ecadin_energy.dashboard.validation import validate_dashboard_directory


def promote_dashboard_staging(
    *,
    project_root: str | Path | None = None,
    config_path: str | Path | None = None,
) -> dict[str, object]:
    config = load_dashboard_config(config_path, project_root=project_root)
    paths = config.paths(project_root)
    validate_dashboard_directory(paths.staging, project_root=paths.root, config_path=config_path)

    archive: Path | None = None
    if paths.production.is_dir() and any(paths.production.iterdir()):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
        archive_root = paths.root / "outputs/dashboard/backups/production"
        archive = archive_root / stamp
        counter = 1
        while archive.exists():
            archive = archive_root / f"{stamp}-{counter}"
            counter += 1
        shutil.copytree(paths.production, archive)

    paths.production.mkdir(parents=True, exist_ok=True)
    for name in DETERMINISTIC_FILES:
        atomic_copy(paths.staging / name, paths.production / name)
    checks = validate_dashboard_directory(paths.production, project_root=paths.root, config_path=config_path)
    summary = {
        "status": "promoted",
        "files": len(DETERMINISTIC_FILES),
        "checks_passed": int(checks["passed"].sum()),
        "checks_total": int(len(checks)),
        "archive": str(archive) if archive else None,
        "production_hashes": {
            name: sha256_file(paths.production / name) for name in DETERMINISTIC_FILES
        },
    }
    write_json(summary, paths.reports / "dashboard_promotion_summary.json")
    return summary
