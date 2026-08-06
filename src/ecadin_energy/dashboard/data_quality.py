from __future__ import annotations

import pandas as pd


def build_quality_summary(detail: pd.DataFrame) -> pd.DataFrame:
    summary = (
        detail.groupby(["year", "data_type", "quality"], dropna=False)
        .size()
        .rename("region_rows")
        .reset_index()
    )
    totals = detail.groupby("year").agg(
        complete_pairs=("available", "sum"),
        total_regions=("region_id", "nunique"),
        attention_rows=("attention", "sum"),
    ).reset_index()
    summary = summary.merge(totals, on="year", how="left")
    return summary.sort_values(["year", "quality"], kind="stable").reset_index(drop=True)


def build_quality_review(detail: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "region_id", "display_name", "year", "data_type", "demand_value_status",
        "supply_value_status", "quality", "quality_badge", "interpolated", "available",
        "attention", "attention_reason",
    ]
    return detail.loc[
        detail["quality"].ne("observed") | detail["attention"], columns
    ].reset_index(drop=True)
