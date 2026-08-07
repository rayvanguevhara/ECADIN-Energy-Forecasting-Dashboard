from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from ecadin_energy.config import PATHS
from ecadin_energy.data_processing.cleaning.distributed_electricity import (
    build_distributed_electricity,
    validate_distributed_electricity,
)
from ecadin_energy.data_processing.cleaning.electricity_customers import (
    build_electricity_customers,
    validate_electricity_customers,
)
from ecadin_energy.data_processing.cleaning.electricity_sold import (
    build_electricity_sold,
    validate_electricity_sold,
)
from ecadin_energy.data_processing.cleaning.installed_capacity import (
    build_installed_capacity,
    validate_installed_capacity,
)
from ecadin_energy.data_processing.cleaning.local_generation import (
    build_local_generation,
    validate_local_generation,
)
from ecadin_energy.data_processing.mastering.canonical_masters import (
    build_canonical_masters,
    validate_canonical_masters,
)
from ecadin_energy.data_processing.reference import validate_reference_layer


BuildFunction = Callable[..., dict[str, Any]]
ValidateFunction = Callable[..., dict[str, Any]]


DATASETS: tuple[tuple[str, BuildFunction, ValidateFunction], ...] = (
    (
        "distributed_electricity",
        build_distributed_electricity,
        validate_distributed_electricity,
    ),
    ("local_generation", build_local_generation, validate_local_generation),
    (
        "installed_capacity",
        build_installed_capacity,
        validate_installed_capacity,
    ),
    ("electricity_sold", build_electricity_sold, validate_electricity_sold),
    (
        "electricity_customers",
        build_electricity_customers,
        validate_electricity_customers,
    ),
)


def _root(project_root: str | Path | None) -> Path:
    return Path(project_root).resolve() if project_root else PATHS.root


def _write_json(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _check_row(
    stage: str,
    result: dict[str, Any],
    details: str,
) -> dict[str, object]:
    return {
        "stage": stage,
        "check_id": f"{stage}_validation",
        "passed": True,
        "observed": json.dumps(result, ensure_ascii=False, default=str),
        "expected": "validation completed without exception",
        "details": details,
    }


def validate_data_pipeline(
    *,
    project_root: str | Path | None = None,
) -> pd.DataFrame:
    root = _root(project_root)
    checks: list[dict[str, object]] = []

    reference = validate_reference_layer(project_root=root)
    checks.append(
        _check_row(
            "reference_layer",
            reference,
            "The 34-region reference layer and file hashes are valid.",
        )
    )

    for dataset_id, _, validate in DATASETS:
        result = validate(project_root=root)
        checks.append(
            _check_row(
                dataset_id,
                result,
                "Processed dataset, lineage, quality, and source contract are valid.",
            )
        )

    canonical = validate_canonical_masters(project_root=root)
    checks.append(
        _check_row(
            "canonical_masters",
            canonical,
            "Regional and national canonical master contracts are valid.",
        )
    )

    frame = pd.DataFrame(checks)
    report_path = root / "outputs/reports/release/data_validation_checks.csv"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(report_path, index=False, encoding="utf-8", lineterminator="\n")
    return frame


def run_data_pipeline(
    *,
    project_root: str | Path | None = None,
) -> dict[str, Any]:
    root = _root(project_root)
    reference = validate_reference_layer(project_root=root)
    builds: dict[str, dict[str, Any]] = {}
    validations: dict[str, dict[str, Any]] = {}

    for dataset_id, build, validate in DATASETS:
        builds[dataset_id] = build(project_root=root)
        validations[dataset_id] = validate(project_root=root)

    canonical_build = build_canonical_masters(project_root=root)
    canonical_validation = validate_canonical_masters(project_root=root)
    checks = validate_data_pipeline(project_root=root)

    summary = {
        "schema_version": "ecadin_data_pipeline_v1",
        "status": "completed",
        "reference_layer": reference,
        "dataset_builds": builds,
        "dataset_validations": validations,
        "canonical_build": canonical_build,
        "canonical_validation": canonical_validation,
        "checks_passed": int(checks["passed"].sum()),
        "checks_total": int(len(checks)),
        "silent_imputation": False,
        "legacy_project_modified": False,
    }
    _write_json(
        summary,
        root / "outputs/reports/release/data_pipeline_summary.json",
    )
    return summary
