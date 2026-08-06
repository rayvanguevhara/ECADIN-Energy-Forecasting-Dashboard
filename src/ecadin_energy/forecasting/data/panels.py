from __future__ import annotations

from dataclasses import asdict

import numpy as np
import pandas as pd

from ecadin_energy.forecasting.configuration import (
    MissingDataPolicy,
    ProductionConfig,
)
from ecadin_energy.forecasting.exceptions import ContractError


PANEL_COLUMNS = [
    "domain",
    "dataset_id",
    "region_id",
    "region_name",
    "modeling_order",
    "year",
    "actual_gwh",
    "training_gwh",
    "target_status",
    "is_observed_target",
    "is_interpolated_target",
    "is_geography_consistent",
    "training_eligible",
    "validation_eligible",
]


def _interpolate_selected_year(
    group: pd.DataFrame,
    *,
    year: int,
) -> float | None:
    previous = group.loc[group["year"] == year - 1, "training_gwh"]
    following = group.loc[group["year"] == year + 1, "training_gwh"]
    if previous.empty or following.empty:
        return None
    previous_value = previous.iloc[0]
    following_value = following.iloc[0]
    if pd.isna(previous_value) or pd.isna(following_value):
        return None
    return (float(previous_value) + float(following_value)) / 2.0


def build_modeling_panel(
    master: pd.DataFrame,
    regions: pd.DataFrame,
    *,
    domain: str,
    dataset_id: str,
    target_column: str,
    policy: MissingDataPolicy,
    history_start_year: int,
    history_end_year: int,
) -> pd.DataFrame:
    required_master = {"region_id", "year", target_column}
    missing_master = sorted(required_master - set(master.columns))
    if missing_master:
        raise ContractError(
            f"Cannot build {domain} panel; missing master columns: "
            f"{missing_master}"
        )
    required_regions = {
        "region_id",
        "canonical_region_name",
        "modeling_order",
    }
    missing_regions = sorted(required_regions - set(regions.columns))
    if missing_regions:
        raise ContractError(
            f"Cannot build {domain} panel; missing region columns: "
            f"{missing_regions}"
        )

    years = range(history_start_year, history_end_year + 1)
    key_grid = pd.MultiIndex.from_product(
        [regions["region_id"].tolist(), list(years)],
        names=["region_id", "year"],
    ).to_frame(index=False)
    source = master[["region_id", "year", target_column]].copy()
    frame = key_grid.merge(
        source,
        on=["region_id", "year"],
        how="left",
        validate="one_to_one",
    )
    frame = frame.merge(
        regions[
            [
                "region_id",
                "canonical_region_name",
                "modeling_order",
            ]
        ],
        on="region_id",
        how="left",
        validate="many_to_one",
    )
    frame = frame.rename(
        columns={
            target_column: "actual_gwh",
            "canonical_region_name": "region_name",
        }
    )
    frame["domain"] = domain
    frame["dataset_id"] = dataset_id
    frame["training_gwh"] = frame["actual_gwh"]

    excluded = (
        frame["region_id"].isin(policy.exclude_pre_year_regions)
        & frame["year"].lt(policy.exclude_before_year)
    )
    frame["is_geography_consistent"] = ~excluded
    frame.loc[excluded, "training_gwh"] = np.nan

    frame["target_status"] = np.where(
        frame["actual_gwh"].notna(),
        "observed",
        "unavailable",
    )
    frame.loc[
        excluded & frame["actual_gwh"].notna(),
        "target_status",
    ] = "excluded_geography_break"

    for region_id, group in frame.groupby("region_id", sort=False):
        for year in policy.interpolate_years:
            row_mask = (
                frame["region_id"].eq(region_id)
                & frame["year"].eq(year)
            )
            if not row_mask.any():
                continue
            row_index = frame.index[row_mask][0]
            if pd.notna(frame.at[row_index, "actual_gwh"]):
                continue
            if not bool(frame.at[row_index, "is_geography_consistent"]):
                continue
            value = _interpolate_selected_year(group, year=year)
            if value is None:
                continue
            frame.at[row_index, "training_gwh"] = value
            frame.at[row_index, "target_status"] = "interpolated"

    frame["is_observed_target"] = (
        frame["actual_gwh"].notna()
        & frame["is_geography_consistent"]
    )
    frame["is_interpolated_target"] = frame["target_status"].eq(
        "interpolated"
    )
    frame["training_eligible"] = frame["training_gwh"].notna()
    frame["validation_eligible"] = frame["is_observed_target"]

    result = frame[PANEL_COLUMNS].copy()
    result = result.sort_values(
        ["modeling_order", "year"]
    ).reset_index(drop=True)
    return result


def build_demand_panel(
    master: pd.DataFrame,
    regions: pd.DataFrame,
    config: ProductionConfig,
) -> pd.DataFrame:
    return build_modeling_panel(
        master,
        regions,
        domain="demand",
        dataset_id=config.demand.dataset_id,
        target_column=config.demand.target_column,
        policy=config.missing_data,
        history_start_year=config.history_start_year,
        history_end_year=config.history_end_year,
    )


def build_supply_panel(
    master: pd.DataFrame,
    regions: pd.DataFrame,
    config: ProductionConfig,
) -> pd.DataFrame:
    return build_modeling_panel(
        master,
        regions,
        domain="supply",
        dataset_id=config.supply.dataset_id,
        target_column=config.supply.target_column,
        policy=config.missing_data,
        history_start_year=config.history_start_year,
        history_end_year=config.history_end_year,
    )
