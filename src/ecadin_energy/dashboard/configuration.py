from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ecadin_energy.config import PATHS
from ecadin_energy.dashboard.contracts import DashboardContractError, DashboardPaths


@dataclass(frozen=True)
class DashboardConfig:
    schema_version: str
    frontend_schema_version: str
    source_dashboard_stage: str
    history_start_year: int
    history_end_year: int
    forecast_start_year: int
    forecast_end_year: int
    expected_regions: int
    modeling_geography: str
    staging_directory: str
    production_directory: str
    reports_directory: str
    frontend_directory: str
    frontend_dataset_path: str
    frontend_geojson_path: str
    regional_uncertainty_display_allowed: bool
    legacy_model_reused: bool
    population_available: bool
    far_above_threshold: float
    above_threshold: float
    below_threshold: float
    far_below_threshold: float
    accounting_disclaimer: str
    allowed_frontend_mutations: tuple[str, ...]
    excluded_frontend_snapshot_directories: tuple[str, ...]

    @property
    def years(self) -> tuple[int, ...]:
        return tuple(range(self.history_start_year, self.forecast_end_year + 1))

    @property
    def forecast_years(self) -> tuple[int, ...]:
        return tuple(range(self.forecast_start_year, self.forecast_end_year + 1))

    def paths(self, project_root: str | Path | None = None) -> DashboardPaths:
        root = Path(project_root).resolve() if project_root else PATHS.root
        frontend = root / self.frontend_directory
        return DashboardPaths(
            root=root,
            staging=root / self.staging_directory,
            production=root / self.production_directory,
            reports=root / self.reports_directory,
            frontend=frontend,
            frontend_dataset=frontend / self.frontend_dataset_path,
            frontend_geojson=frontend / self.frontend_geojson_path,
        )


def _required(mapping: dict[str, Any], key: str) -> Any:
    if key not in mapping:
        raise DashboardContractError(f"Missing dashboard config key: {key}")
    return mapping[key]


def load_dashboard_config(
    path: str | Path | None = None,
    *,
    project_root: str | Path | None = None,
) -> DashboardConfig:
    root = Path(project_root).resolve() if project_root else PATHS.root
    config_path = Path(path) if path else root / "configs/dashboard/production.json"
    if not config_path.is_absolute():
        config_path = root / config_path
    if not config_path.is_file():
        raise FileNotFoundError(f"Dashboard config not found: {config_path}")
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    thresholds = _required(raw, "category_thresholds_percent")
    config = DashboardConfig(
        schema_version=str(_required(raw, "schema_version")),
        frontend_schema_version=str(_required(raw, "frontend_schema_version")),
        source_dashboard_stage=str(_required(raw, "source_dashboard_stage")),
        history_start_year=int(_required(raw, "history_start_year")),
        history_end_year=int(_required(raw, "history_end_year")),
        forecast_start_year=int(_required(raw, "forecast_start_year")),
        forecast_end_year=int(_required(raw, "forecast_end_year")),
        expected_regions=int(_required(raw, "expected_regions")),
        modeling_geography=str(_required(raw, "modeling_geography")),
        staging_directory=str(_required(raw, "staging_directory")),
        production_directory=str(_required(raw, "production_directory")),
        reports_directory=str(_required(raw, "reports_directory")),
        frontend_directory=str(_required(raw, "frontend_directory")),
        frontend_dataset_path=str(_required(raw, "frontend_dataset_path")),
        frontend_geojson_path=str(_required(raw, "frontend_geojson_path")),
        regional_uncertainty_display_allowed=bool(_required(raw, "regional_uncertainty_display_allowed")),
        legacy_model_reused=bool(_required(raw, "legacy_model_reused")),
        population_available=bool(_required(raw, "population_available")),
        far_above_threshold=float(_required(thresholds, "far_above")),
        above_threshold=float(_required(thresholds, "above")),
        below_threshold=float(_required(thresholds, "below")),
        far_below_threshold=float(_required(thresholds, "far_below")),
        accounting_disclaimer=str(_required(raw, "accounting_disclaimer")),
        allowed_frontend_mutations=tuple(str(v) for v in _required(raw, "allowed_frontend_mutations")),
        excluded_frontend_snapshot_directories=tuple(str(v) for v in _required(raw, "excluded_frontend_snapshot_directories")),
    )
    validate_dashboard_config(config)
    return config


def validate_dashboard_config(config: DashboardConfig) -> None:
    failures: list[str] = []
    if config.history_end_year + 1 != config.forecast_start_year:
        failures.append("forecast_start_year must follow history_end_year")
    if config.forecast_start_year > config.forecast_end_year:
        failures.append("forecast_start_year must not exceed forecast_end_year")
    if config.expected_regions <= 0:
        failures.append("expected_regions must be positive")
    if not (
        config.far_below_threshold < config.below_threshold
        < config.above_threshold < config.far_above_threshold
    ):
        failures.append("category thresholds are not strictly increasing")
    if config.regional_uncertainty_display_allowed:
        failures.append("regional uncertainty display must remain disabled")
    if config.population_available:
        failures.append("population must remain backlog until canonical integration")
    if tuple(config.allowed_frontend_mutations) != ("src/data/dashboard-production.json",):
        failures.append("only dashboard-production.json may be mutated by refresh")
    if failures:
        raise DashboardContractError(" | ".join(failures))
