from __future__ import annotations

import pandas as pd


def build_map_timeseries(detail: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "region_id", "display_name", "island_group", "latitude", "longitude", "year",
        "data_type", "demand_gwh", "supply_gwh", "accounting_difference_gwh",
        "difference_to_demand_percent", "supply_to_demand_ratio", "available",
        "quality", "gap_category", "attention", "attention_reason",
    ]
    return detail[columns].copy()
