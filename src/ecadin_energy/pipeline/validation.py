from __future__ import annotations

from pathlib import Path

from ecadin_energy.config import PATHS
from ecadin_energy.forecasting.configuration import (
    load_production_config,
)
from ecadin_energy.forecasting.production.validation import (
    validate_written_outputs,
)


def validate_production_pipeline(
    *,
    project_root: str | Path | None = None,
    config_path: str | Path | None = None,
):
    root = Path(project_root).resolve() if project_root else PATHS.root
    config = load_production_config(
        config_path,
        project_root=root,
    )
    return validate_written_outputs(
        project_root=root,
        config=config,
    )
