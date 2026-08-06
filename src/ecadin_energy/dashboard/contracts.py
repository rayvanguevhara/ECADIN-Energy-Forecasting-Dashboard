from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class DashboardContractError(ValueError):
    """Raised when a dashboard production contract is violated."""


@dataclass(frozen=True)
class DashboardPaths:
    root: Path
    staging: Path
    production: Path
    reports: Path
    frontend: Path
    frontend_dataset: Path
    frontend_geojson: Path


@dataclass(frozen=True)
class DashboardBuildResult:
    staging_rows: int
    national_rows: int
    regions: int
    complete_pairs: int
    historical_incomplete_pairs: int
    production_files: tuple[Path, ...]
    frontend_dataset: Path | None = None


DETAIL_COLUMNS = (
    "region_id",
    "source_name",
    "display_name",
    "island_group",
    "latitude",
    "longitude",
    "year",
    "data_type",
    "demand_gwh",
    "supply_gwh",
    "accounting_difference_gwh",
    "difference_to_demand_percent",
    "supply_to_demand_ratio",
    "available",
    "quality",
    "quality_badge",
    "interpolated",
    "attention",
    "attention_reason",
    "population_jiwa",
    "demand_model",
    "supply_model",
    "demand_value_status",
    "supply_value_status",
)
