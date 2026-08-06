from __future__ import annotations

import pandas as pd


def build_regional_ranking(detail: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "region_id", "display_name", "island_group", "year", "data_type",
        "demand_gwh", "supply_gwh", "accounting_difference_gwh",
        "difference_to_demand_percent", "supply_to_demand_ratio", "available",
        "quality", "gap_category", "attention", "attention_reason",
    ]
    ranking = detail[columns].copy()
    ranking["demand_rank_desc"] = ranking.groupby("year")["demand_gwh"].rank(
        method="min", ascending=False, na_option="bottom"
    )
    ranking["supply_rank_desc"] = ranking.groupby("year")["supply_gwh"].rank(
        method="min", ascending=False, na_option="bottom"
    )
    ranking["difference_rank_desc"] = ranking.groupby("year")[
        "accounting_difference_gwh"
    ].rank(method="min", ascending=False, na_option="bottom")
    ranking.loc[~ranking["available"], "difference_rank_desc"] = pd.NA
    return ranking
