from __future__ import annotations

import numpy as np
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


def build_national_timeseries(detail: pd.DataFrame, expected_regions: int) -> pd.DataFrame:
    """Build annual national totals and matched-region YoY growth rates."""
    rows: list[dict[str, object]] = []
    complete_by_year: dict[int, pd.DataFrame] = {}

    working = detail.copy()
    working["year"] = pd.to_numeric(working["year"], errors="raise").astype(int)
    working["demand_gwh"] = pd.to_numeric(working["demand_gwh"], errors="coerce")
    working["supply_gwh"] = pd.to_numeric(working["supply_gwh"], errors="coerce")
    working["_available_bool"] = _to_bool_series(working["available"])

    for year, group in working.groupby("year", sort=True):
        year_int = int(year)
        complete = group.loc[group["_available_bool"]].copy()
        demand = float(complete["demand_gwh"].sum())
        supply = float(complete["supply_gwh"].sum())
        difference = supply - demand
        ratio = supply / demand if demand else np.nan
        gap_pct = difference / demand * 100.0 if demand else np.nan

        complete_by_year[year_int] = complete.set_index("region_id")[["demand_gwh", "supply_gwh"]]
        rows.append(
            {
                "year": year_int,
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

    demand_yoy_list: list[float] = []
    supply_yoy_list: list[float] = []
    yoy_common_regions_list: list[object] = []
    yoy_basis_list: list[str] = []

    prev_year: int | None = None
    for year_int in frame["year"].tolist():
        if prev_year is None:
            demand_yoy_list.append(np.nan)
            supply_yoy_list.append(np.nan)
            yoy_common_regions_list.append(pd.NA)
            yoy_basis_list.append("first_year")
        else:
            prev_df = complete_by_year[prev_year]
            curr_df = complete_by_year[year_int]
            common_ids = sorted(set(curr_df.index) & set(prev_df.index))
            if common_ids:
                prev_d = float(prev_df.loc[common_ids, "demand_gwh"].sum())
                curr_d = float(curr_df.loc[common_ids, "demand_gwh"].sum())
                prev_s = float(prev_df.loc[common_ids, "supply_gwh"].sum())
                curr_s = float(curr_df.loc[common_ids, "supply_gwh"].sum())
                demand_yoy = (curr_d - prev_d) / prev_d * 100.0 if prev_d > 0.0 else np.nan
                supply_yoy = (curr_s - prev_s) / prev_s * 100.0 if prev_s > 0.0 else np.nan
            else:
                demand_yoy = np.nan
                supply_yoy = np.nan

            demand_yoy_list.append(demand_yoy)
            supply_yoy_list.append(supply_yoy)
            yoy_common_regions_list.append(len(common_ids))
            if (
                len(common_ids) == expected_regions
                and len(curr_df) == expected_regions
                and len(prev_df) == expected_regions
            ):
                yoy_basis_list.append("matched_complete_regions")
            else:
                yoy_basis_list.append("partial_overlap_matched")
        prev_year = year_int

    frame["demand_growth_yoy_percent"] = demand_yoy_list
    frame["supply_growth_yoy_percent"] = supply_yoy_list
    frame["yoy_common_regions"] = pd.Series(yoy_common_regions_list, dtype="Int64")
    frame["yoy_basis"] = yoy_basis_list
    return frame
