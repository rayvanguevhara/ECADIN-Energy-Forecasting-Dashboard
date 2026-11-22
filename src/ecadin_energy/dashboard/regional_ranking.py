from __future__ import annotations

import pandas as pd


def _to_bool_series(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False).astype(bool)
    return (
        series.astype("string")
        .str.strip()
        .str.lower()
        .eq("true")
        .fillna(False)
    )


def build_regional_ranking(detail: pd.DataFrame) -> pd.DataFrame:
    """Build annual regional rankings while keeping missing metrics unranked (NA)."""
    columns = [
        "region_id", "display_name", "island_group", "year", "data_type",
        "demand_gwh", "supply_gwh", "accounting_difference_gwh",
        "difference_to_demand_percent", "supply_to_demand_ratio", "available",
        "quality", "gap_category", "attention", "attention_reason",
    ]
    ranking = detail[columns].copy()
    ranking["demand_gwh"] = pd.to_numeric(ranking["demand_gwh"], errors="coerce")
    ranking["supply_gwh"] = pd.to_numeric(ranking["supply_gwh"], errors="coerce")
    ranking["accounting_difference_gwh"] = pd.to_numeric(
        ranking["accounting_difference_gwh"], errors="coerce"
    )
    available_mask = _to_bool_series(ranking["available"])

    ranking["demand_rank_desc"] = ranking.groupby("year")["demand_gwh"].rank(
        method="min", ascending=False, na_option="keep"
    )
    ranking["supply_rank_desc"] = ranking.groupby("year")["supply_gwh"].rank(
        method="min", ascending=False, na_option="keep"
    )
    ranking["difference_rank_desc"] = ranking.groupby("year")[
        "accounting_difference_gwh"
    ].rank(method="min", ascending=False, na_option="keep")

    ranking.loc[ranking["demand_gwh"].isna(), "demand_rank_desc"] = pd.NA
    ranking.loc[ranking["supply_gwh"].isna(), "supply_rank_desc"] = pd.NA
    ranking.loc[~available_mask, "difference_rank_desc"] = pd.NA
    return ranking
