from __future__ import annotations

from pathlib import Path

import pandas as pd

from ecadin_energy.config import PATHS
from ecadin_energy.forecasting.exceptions import ContractError


REGIONAL_MASTER_COLUMNS = {
    "region_id",
    "year",
    "distributed_electricity_gwh",
    "local_generation_gwh",
    "installed_capacity_mw",
}
REGION_REFERENCE_COLUMNS = {
    "region_id",
    "canonical_region_name",
    "display_name",
    "modeling_order",
    "is_model_region",
}


def _root(project_root: str | Path | None) -> Path:
    return Path(project_root).resolve() if project_root else PATHS.root


def load_regional_master(
    *,
    project_root: str | Path | None = None,
    path: str | Path | None = None,
) -> pd.DataFrame:
    root = _root(project_root)
    source = (
        Path(path)
        if path is not None
        else root / "data/processed/master/regional_energy_master.csv"
    )
    if not source.is_absolute():
        source = root / source
    if not source.is_file():
        raise FileNotFoundError(f"Regional master not found: {source}")

    frame = pd.read_csv(source, low_memory=False)
    missing = sorted(REGIONAL_MASTER_COLUMNS - set(frame.columns))
    if missing:
        raise ContractError(
            f"Regional master is missing required columns: {missing}"
        )
    frame = frame[list(REGIONAL_MASTER_COLUMNS)].copy()
    frame["region_id"] = (
        frame["region_id"].astype("string").str.strip().str.upper()
    )
    frame["year"] = pd.to_numeric(frame["year"], errors="raise").astype(int)
    for column in (
        "distributed_electricity_gwh",
        "local_generation_gwh",
        "installed_capacity_mw",
    ):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if frame.duplicated(["region_id", "year"]).any():
        raise ContractError("Duplicate region_id-year keys in regional master")
    return frame.sort_values(["region_id", "year"]).reset_index(drop=True)


def load_regions(
    *,
    project_root: str | Path | None = None,
    path: str | Path | None = None,
) -> pd.DataFrame:
    root = _root(project_root)
    source = (
        Path(path)
        if path is not None
        else root / "data/reference/regions.csv"
    )
    if not source.is_absolute():
        source = root / source
    if not source.is_file():
        raise FileNotFoundError(f"Region reference not found: {source}")

    frame = pd.read_csv(source, low_memory=False)
    missing = sorted(REGION_REFERENCE_COLUMNS - set(frame.columns))
    if missing:
        raise ContractError(
            f"Region reference is missing required columns: {missing}"
        )
    frame["region_id"] = (
        frame["region_id"].astype("string").str.strip().str.upper()
    )
    frame["modeling_order"] = pd.to_numeric(
        frame["modeling_order"],
        errors="raise",
    ).astype(int)
    model_flag = (
        frame["is_model_region"]
        if frame["is_model_region"].dtype == bool
        else frame["is_model_region"]
        .astype("string")
        .str.strip()
        .str.lower()
        .map({"true": True, "false": False, "1": True, "0": False})
        .fillna(False)
        .astype(bool)
    )
    frame = frame.loc[model_flag].copy()
    if frame["region_id"].duplicated().any():
        raise ContractError("Duplicate region_id in region reference")
    return frame.sort_values("modeling_order").reset_index(drop=True)
