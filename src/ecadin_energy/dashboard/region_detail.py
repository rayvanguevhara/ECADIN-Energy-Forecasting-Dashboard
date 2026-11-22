from __future__ import annotations

import numpy as np
import pandas as pd

from ecadin_energy.dashboard.configuration import DashboardConfig
from ecadin_energy.dashboard.contracts import DashboardContractError, DETAIL_COLUMNS


VALID_GAP_CATEGORIES = (
    "jauh_di_atas_demand",
    "di_atas_demand",
    "relatif_seimbang",
    "di_bawah_demand",
    "jauh_di_bawah_demand",
    "tidak_tersedia",
)
ATTENTION_GAP_CATEGORIES = frozenset(
    {
        "jauh_di_bawah_demand",
        "jauh_di_atas_demand",
        "tidak_tersedia",
    }
)
ATTENTION_REASON_MAP = {
    "jauh_di_bawah_demand": "jauh_di_bawah_demand_perlu_konteks_interkoneksi",
    "jauh_di_atas_demand": "jauh_di_atas_demand_perlu_konteks_interkoneksi",
    "tidak_tersedia": "gap_tidak_lengkap",
}


def classify_accounting_difference(value: float | None, config: DashboardConfig) -> str:
    if value is None or not np.isfinite(value):
        return "tidak_tersedia"
    if value >= config.far_above_threshold:
        return "jauh_di_atas_demand"
    if value >= config.above_threshold:
        return "di_atas_demand"
    if value > config.below_threshold:
        return "relatif_seimbang"
    if value > config.far_below_threshold:
        return "di_bawah_demand"
    return "jauh_di_bawah_demand"


def build_region_detail(
    combined: pd.DataFrame,
    regions: pd.DataFrame,
    config: DashboardConfig,
) -> pd.DataFrame:
    required = {
        "region_id", "region_name", "year", "data_type", "demand_gwh", "supply_gwh",
        "accounting_difference_gwh", "demand_available", "supply_available",
        "difference_available", "demand_status", "supply_status", "demand_interpolated",
        "supply_interpolated", "demand_model_id", "supply_model_id",
    }
    missing = sorted(required.difference(combined.columns))
    if missing:
        raise DashboardContractError(f"Combined forecast missing columns: {missing}")

    region_columns = [
        "region_id", "canonical_region_name", "display_name", "island_group",
        "latitude", "longitude", "is_model_region",
    ]
    region_reference = regions[region_columns].copy()
    region_reference = region_reference.loc[
        region_reference["is_model_region"].astype(str).str.lower().eq("true")
    ]
    detail = combined.merge(region_reference, on="region_id", how="left", validate="many_to_one")
    if detail["display_name"].isna().any():
        missing_ids = sorted(detail.loc[detail["display_name"].isna(), "region_id"].unique())
        raise DashboardContractError(f"Region reference missing IDs: {missing_ids}")

    for column in ["demand_gwh", "supply_gwh", "accounting_difference_gwh"]:
        detail[column] = pd.to_numeric(detail[column], errors="coerce")
    for column in [
        "demand_available", "supply_available", "difference_available",
        "demand_interpolated", "supply_interpolated",
    ]:
        detail[column] = detail[column].astype(str).str.lower().eq("true")

    detail["available"] = detail["difference_available"]
    detail["difference_to_demand_percent"] = np.where(
        detail["available"] & detail["demand_gwh"].ne(0),
        detail["accounting_difference_gwh"] / detail["demand_gwh"] * 100.0,
        np.nan,
    )
    detail["supply_to_demand_ratio"] = np.where(
        detail["available"] & detail["demand_gwh"].ne(0),
        detail["supply_gwh"] / detail["demand_gwh"],
        np.nan,
    )
    detail["interpolated"] = detail["demand_interpolated"] | detail["supply_interpolated"]
    detail["quality"] = np.select(
        [
            detail["data_type"].eq("forecast"),
            ~detail["available"],
            detail["interpolated"],
        ],
        ["forecast", "incomplete", "interpolated"],
        default="observed",
    )
    detail["quality_badge"] = detail["quality"].map(
        {
            "forecast": "production_forecast",
            "incomplete": "incomplete_pair",
            "interpolated": "includes_interpolation",
            "observed": "observed_complete",
        }
    )
    detail["gap_category"] = [
        classify_accounting_difference(value, config)
        for value in detail["difference_to_demand_percent"]
    ]
    detail["attention"] = detail["gap_category"].isin(ATTENTION_GAP_CATEGORIES)
    detail["attention_reason"] = detail["gap_category"].map(ATTENTION_REASON_MAP)
    detail["population_jiwa"] = np.nan
    detail["demand_model"] = np.where(
        detail["data_type"].eq("forecast"), detail["demand_model_id"], "historical_series"
    )
    detail["supply_model"] = np.where(
        detail["data_type"].eq("forecast"), detail["supply_model_id"], "historical_series"
    )
    detail["source_name"] = detail["canonical_region_name"]
    detail["demand_value_status"] = detail["demand_status"]
    detail["supply_value_status"] = detail["supply_status"]
    detail["year"] = detail["year"].astype(int)

    result = detail[list(DETAIL_COLUMNS) + ["gap_category", "modeling_order"]].copy()
    result = result.sort_values(["modeling_order", "year"], kind="stable").reset_index(drop=True)
    return result
