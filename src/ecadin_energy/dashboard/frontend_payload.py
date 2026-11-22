from __future__ import annotations

from typing import Any

import pandas as pd

from ecadin_energy.dashboard.configuration import DashboardConfig
from ecadin_energy.dashboard.methodology import build_methodology, frontend_metadata
from ecadin_energy.dashboard.serializers import clean_scalar, records
from ecadin_energy.forecasting.configuration import ProductionConfig


def _point(row: pd.Series) -> dict[str, Any]:
    return {
        "year": int(row["year"]),
        "demand_gwh": clean_scalar(row["demand_gwh"]),
        "supply_gwh": clean_scalar(row["supply_gwh"]),
        "gap_gwh": clean_scalar(row["accounting_difference_gwh"]),
        "gap_pct": clean_scalar(row["difference_to_demand_percent"]),
        "ratio": clean_scalar(row["supply_to_demand_ratio"]),
        "data_type": str(row["data_type"]),
        "forecast": str(row["data_type"]) == "forecast",
        "available": bool(row["available"]),
        "quality": str(row["quality"]),
        "quality_badge": str(row["quality_badge"]),
        "gap_category": str(row["gap_category"]),
        "interpolated": bool(row["interpolated"]),
        "attention": bool(row["attention"]),
        "attention_reason": clean_scalar(row["attention_reason"]),
        "population_jiwa": None,
        "demand_model": clean_scalar(row["demand_model"]),
        "supply_model": clean_scalar(row["supply_model"]),
        "demand_value_status": clean_scalar(row["demand_value_status"]),
        "supply_value_status": clean_scalar(row["supply_value_status"]),
    }


def build_frontend_payload(
    detail: pd.DataFrame,
    national: pd.DataFrame,
    models: pd.DataFrame,
    source_hashes: dict[str, str],
    config: DashboardConfig,
    *,
    forecast_config: ProductionConfig | None = None,
    quality_flags: pd.DataFrame | None = None,
    quality_flags_summary: pd.DataFrame | None = None,
    quality_flags_highlights: pd.DataFrame | None = None,
    methodology: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble frontend production JSON payload with additive V2/quality/methodology fields."""
    provinces: list[dict[str, Any]] = []
    for region_id, group in detail.groupby("region_id", sort=False):
        first = group.iloc[0]
        provinces.append(
            {
                "code": str(region_id),
                "source_name": str(first["source_name"]),
                "name": str(first["display_name"]),
                "island": str(first["island_group"]),
                "lat": float(first["latitude"]),
                "lng": float(first["longitude"]),
                "population_2030_jiwa": None,
                "series": [_point(row) for _, row in group.sort_values("year").iterrows()],
            }
        )

    national_rows = [
        {
            "year": int(row["year"]),
            "demand_gwh": float(row["demand_gwh"]),
            "supply_gwh": float(row["supply_gwh"]),
            "gap_gwh": float(row["accounting_difference_gwh"]),
            "gap_pct": float(row["difference_to_demand_percent"]),
            "ratio": float(row["supply_to_demand_ratio"]),
            "forecast": bool(row["forecast"]),
            "data_type": str(row["data_type"]),
            "complete_regions": int(row["complete_regions"]),
            "total_regions": int(row["total_regions"]),
            "data_completeness": str(row["data_completeness"]),
            "demand_growth_yoy_percent": clean_scalar(row["demand_growth_yoy_percent"]),
            "supply_growth_yoy_percent": clean_scalar(row["supply_growth_yoy_percent"]),
            "yoy_common_regions": clean_scalar(row["yoy_common_regions"]),
            "yoy_basis": str(row["yoy_basis"]),
        }
        for _, row in national.iterrows()
    ]
    metadata, metadata_v2 = frontend_metadata(
        config,
        models=models,
        forecast_config=forecast_config,
    )
    metadata_v2["row_count"] = str(len(detail))
    metadata_v2["complete_gap_count"] = str(int(detail["available"].sum()))
    metadata_v2["historical_incomplete_gap_count"] = str(
        int((detail["data_type"].eq("historical") & ~detail["available"]).sum())
    )

    resolved_methodology = (
        methodology
        if methodology is not None
        else build_methodology(config, models=models, forecast_config=forecast_config)
    )
    if quality_flags is not None:
        quality_flags_total = int(len(quality_flags))
    elif quality_flags_summary is not None and not quality_flags_summary.empty:
        quality_flags_total = int(
            pd.to_numeric(quality_flags_summary["flag_count"], errors="coerce").fillna(0).sum()
        )
    else:
        quality_flags_total = 0

    legacy_clarification = str(
        resolved_methodology.get("contract_clarifications", {})
        .get("legacy_ridge_used", {})
        .get(
            "meaning",
            "False certifies that the pre-project legacy raw-level Ridge baseline is not reused.",
        )
    )

    return {
        "schema_version": config.frontend_schema_version,
        "generated_at_utc": None,
        "source_dashboard_stage": config.source_dashboard_stage,
        "source_registry_status": "production",
        "production_ready": True,
        "geography": config.modeling_geography,
        "period": [config.history_start_year, config.forecast_end_year],
        "forecast_start": config.forecast_start_year,
        "region_count": config.expected_regions,
        "row_count": int(len(detail)),
        "complete_gap_count": int(detail["available"].sum()),
        "historical_incomplete_gap_count": int(
            (detail["data_type"].eq("historical") & ~detail["available"]).sum()
        ),
        "regional_uncertainty_display_allowed": config.regional_uncertainty_display_allowed,
        "legacy_ridge_used": config.legacy_model_reused,
        "legacy_ridge_clarification": legacy_clarification,
        "source_hashes": source_hashes,
        "provinces": provinces,
        "national": national_rows,
        "models": records(models),
        "quality_flags_total": quality_flags_total,
        "quality_flags_summary": (
            records(quality_flags_summary) if quality_flags_summary is not None else []
        ),
        "quality_flags_highlights": (
            records(quality_flags_highlights) if quality_flags_highlights is not None else []
        ),
        "methodology": resolved_methodology,
        "metadata": metadata,
        "metadata_v2": metadata_v2,
    }
