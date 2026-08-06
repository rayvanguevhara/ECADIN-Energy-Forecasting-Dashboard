from __future__ import annotations

import numpy as np
import pandas as pd


def build_national_timeseries(detail: pd.DataFrame, expected_regions: int) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for year, group in detail.groupby("year", sort=True):
        complete = group.loc[group["available"]].copy()
        demand = float(complete["demand_gwh"].sum())
        supply = float(complete["supply_gwh"].sum())
        difference = supply - demand
        ratio = supply / demand if demand else np.nan
        gap_pct = difference / demand * 100.0 if demand else np.nan
        rows.append(
            {
                "year": int(year),
                "demand_gwh": demand,
                "supply_gwh": supply,
                "accounting_difference_gwh": difference,
                "difference_to_demand_percent": gap_pct,
                "supply_to_demand_ratio": ratio,
                "forecast": bool(group["data_type"].eq("forecast").all()),
                "data_type": str(group["data_type"].iloc[0]),
                "complete_regions": int(len(complete)),
                "total_regions": int(expected_regions),
                "data_completeness": (
                    "complete" if len(complete) == expected_regions else "partial_overlap"
                ),
            }
        )
    frame = pd.DataFrame(rows).sort_values("year").reset_index(drop=True)
    frame["demand_growth_yoy_percent"] = frame["demand_gwh"].pct_change(fill_method=None) * 100.0
    frame["supply_growth_yoy_percent"] = frame["supply_gwh"].pct_change(fill_method=None) * 100.0
    return frame
