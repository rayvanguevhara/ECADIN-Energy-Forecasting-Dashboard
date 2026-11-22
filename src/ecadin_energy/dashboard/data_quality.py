from __future__ import annotations

import numpy as np
import pandas as pd


QUALITY_FLAGS_CANONICAL_COLUMNS = (
    "dataset_id",
    "region_id",
    "year",
    "variable_name",
    "quality_status",
    "issue_type",
    "observed_value",
    "comparison_value",
    "metric_value",
    "treatment",
    "note",
)

QUALITY_FLAGS_SUMMARY_COLUMNS = (
    "dataset_id",
    "issue_type",
    "quality_status",
    "flag_count",
    "first_year",
    "last_year",
    "affected_regions",
)

QUALITY_FLAGS_HIGHLIGHT_COLUMNS = (
    "dataset_id",
    "region_id",
    "display_name",
    "year",
    "variable_name",
    "quality_status",
    "issue_type",
    "observed_value",
    "comparison_value",
    "metric_value",
    "treatment",
    "note",
)

_HIGHLIGHT_ISSUE_TYPES = frozenset(
    {
        "large_zero_base_jump",
        "large_consecutive_yoy_change",
        "national_total_mismatch",
        "missing_source_value",
    }
)

_ISSUE_PRIORITY = {
    "large_zero_base_jump": 0,
    "national_total_mismatch": 1,
    "large_consecutive_yoy_change": 2,
    "missing_source_value": 3,
}


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


def normalize_quality_flags(quality_flags: pd.DataFrame | None) -> pd.DataFrame:
    """Normalize canonical or minimal fixture quality-flag frames to the 11-column schema."""
    if quality_flags is None or quality_flags.empty:
        empty = pd.DataFrame(columns=QUALITY_FLAGS_CANONICAL_COLUMNS)
        empty["year"] = pd.array([], dtype="Int64")
        return empty

    frame = quality_flags.copy()
    if "issue_type" not in frame.columns and "flag_type" in frame.columns:
        frame["issue_type"] = frame["flag_type"]
    if "quality_status" not in frame.columns and "severity" in frame.columns:
        frame["quality_status"] = frame["severity"]
    if "note" not in frame.columns and "message" in frame.columns:
        frame["note"] = frame["message"]

    for column in QUALITY_FLAGS_CANONICAL_COLUMNS:
        if column not in frame.columns:
            frame[column] = pd.NA

    normalized = frame[list(QUALITY_FLAGS_CANONICAL_COLUMNS)].copy()
    normalized["year"] = pd.to_numeric(normalized["year"], errors="coerce").astype("Int64")
    for col in ("observed_value", "comparison_value", "metric_value"):
        normalized[col] = pd.to_numeric(normalized[col], errors="coerce")

    region_series = normalized["region_id"].astype("string").str.strip()
    normalized["region_id"] = region_series.where(
        region_series.notna() & region_series.ne("") & region_series.str.lower().ne("nan"),
        pd.NA,
    )
    return normalized


def build_quality_flags_summary(quality_flags: pd.DataFrame | None) -> pd.DataFrame:
    """Aggregate structured data quality flags by dataset, issue type, and status."""
    normalized = normalize_quality_flags(quality_flags)
    if normalized.empty:
        empty = pd.DataFrame(columns=QUALITY_FLAGS_SUMMARY_COLUMNS)
        for col in ("flag_count", "first_year", "last_year", "affected_regions"):
            empty[col] = pd.array([], dtype="Int64")
        return empty

    rows: list[dict[str, object]] = []
    grouped = normalized.groupby(
        ["dataset_id", "issue_type", "quality_status"], dropna=False, sort=True
    )
    for (dataset_id, issue_type, quality_status), group in grouped:
        years = group["year"].dropna()
        regions = group["region_id"].dropna().astype(str).str.strip()
        regions = regions.loc[regions.ne("")]
        rows.append(
            {
                "dataset_id": str(dataset_id),
                "issue_type": str(issue_type),
                "quality_status": str(quality_status),
                "flag_count": int(len(group)),
                "first_year": int(years.min()) if not years.empty else pd.NA,
                "last_year": int(years.max()) if not years.empty else pd.NA,
                "affected_regions": int(regions.nunique()),
            }
        )

    summary = pd.DataFrame(rows, columns=QUALITY_FLAGS_SUMMARY_COLUMNS)
    for col in ("flag_count", "first_year", "last_year", "affected_regions"):
        summary[col] = pd.array(summary[col].tolist(), dtype="Int64")
    return summary.sort_values(
        ["dataset_id", "issue_type", "quality_status"], kind="stable"
    ).reset_index(drop=True)


def build_quality_flags_highlights(
    quality_flags: pd.DataFrame | None,
    regions: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Extract non-2016 high-signal source audit flags (warnings & missing source values)."""
    normalized = normalize_quality_flags(quality_flags)
    if normalized.empty:
        empty = pd.DataFrame(columns=QUALITY_FLAGS_HIGHLIGHT_COLUMNS)
        empty["year"] = pd.array([], dtype="Int64")
        return empty

    mask = normalized["quality_status"].astype(str).eq("warning") | normalized[
        "issue_type"
    ].astype(str).isin(_HIGHLIGHT_ISSUE_TYPES)
    highlights = normalized.loc[mask].copy()
    if highlights.empty:
        empty = pd.DataFrame(columns=QUALITY_FLAGS_HIGHLIGHT_COLUMNS)
        empty["year"] = pd.array([], dtype="Int64")
        return empty

    if regions is not None and not regions.empty and "region_id" in regions.columns:
        region_map = regions[["region_id", "display_name"]].drop_duplicates("region_id")
        highlights = highlights.merge(region_map, on="region_id", how="left")
    else:
        highlights["display_name"] = pd.NA

    highlights["_priority"] = (
        highlights["issue_type"].astype(str).map(_ISSUE_PRIORITY).fillna(4).astype(int)
    )
    highlights["_region_sort"] = highlights["region_id"].astype("string").fillna("")
    highlights = highlights.sort_values(
        ["_priority", "dataset_id", "year", "_region_sort"],
        ascending=[True, True, False, True],
        kind="stable",
        na_position="last",
    )
    result = highlights[list(QUALITY_FLAGS_HIGHLIGHT_COLUMNS)].reset_index(drop=True)
    result["year"] = pd.array(result["year"].tolist(), dtype="Int64")
    for col in ("observed_value", "comparison_value", "metric_value"):
        result[col] = np.where(
            pd.to_numeric(result[col], errors="coerce").notna(),
            pd.to_numeric(result[col], errors="coerce"),
            np.nan,
        )
    return result
