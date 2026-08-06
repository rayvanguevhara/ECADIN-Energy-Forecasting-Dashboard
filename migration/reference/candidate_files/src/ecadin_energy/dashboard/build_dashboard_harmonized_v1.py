"""Build ECADIN Phase 3I harmonized dashboard staging datasets.

This stage converts the validated Phase 3H combined gap contract into
dashboard-ready CSV files without overwriting the current canonical dashboard
folder. It is the safe bridge between modeling outputs and the Streamlit/React
presentation layer.

Default input
-------------
outputs/gap/phase3h_combined_v1/
    supply_demand_gap_combined_v1_2011_2030.csv
    supply_demand_gap_combined_v1_national_2011_2030.csv
    supply_demand_gap_combined_v1_category_summary_2011_2030.csv
    supply_demand_gap_combined_v1_ranking_deficit_2025_2030.csv
    supply_demand_gap_combined_v1_ranking_surplus_2025_2030.csv
    supply_demand_gap_combined_v1_metadata.json

Default output
--------------
outputs/dashboard/phase3i_harmonized_v1/

Important contracts
-------------------
- 34 harmonized modeling regions.
- Historical period 2011-2024 and forecast period 2025-2030.
- 680 province-year rows.
- 204 complete forecast rows.
- Regional supply uncertainty is not exported to dashboard files because the
  current small-region interval calibration is research-only.
- Legacy Ridge metrics and feature importance are not reused.
- Existing canonical files under outputs/dashboard are not overwritten.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


STAGE_VERSION = "dashboard_harmonized_v1"
SCHEMA_VERSION = "1.0"
EXPECTED_REGION_COUNT = 34
EXPECTED_HISTORICAL_ROWS = 476
EXPECTED_FORECAST_ROWS = 204
EXPECTED_COMBINED_ROWS = 680
EXPECTED_COMPLETE_ROWS = 671
EXPECTED_INCOMPLETE_HISTORICAL_ROWS = 9
EXPECTED_YEARS = list(range(2011, 2031))
FORECAST_YEARS = list(range(2025, 2031))

REGIONAL_UNCERTAINTY_DISPLAY_ALLOWED = False

COORDINATES: dict[str, tuple[float, float]] = {
    "ACEH": (4.6951, 96.7494),
    "SUMATERA UTARA": (2.1154, 99.5451),
    "SUMATERA BARAT": (-0.7399, 100.8000),
    "RIAU": (0.2933, 101.7068),
    "JAMBI": (-1.6101, 103.6131),
    "SUMATERA SELATAN": (-3.3194, 104.9144),
    "BENGKULU": (-3.5778, 102.3464),
    "LAMPUNG": (-4.5586, 105.4068),
    "KEP. BANGKA BELITUNG": (-2.7411, 106.4406),
    "KEPULAUAN BANGKA BELITUNG": (-2.7411, 106.4406),
    "KEP. RIAU": (3.9457, 108.1429),
    "KEPULAUAN RIAU": (3.9457, 108.1429),
    "DKI JAKARTA": (-6.2088, 106.8456),
    "JAWA BARAT": (-6.9147, 107.6098),
    "JAWA TENGAH": (-7.1500, 110.1403),
    "DI YOGYAKARTA": (-7.8754, 110.4262),
    "JAWA TIMUR": (-7.5361, 112.2384),
    "BANTEN": (-6.4058, 106.0640),
    "BALI": (-8.3405, 115.0920),
    "NUSA TENGGARA BARAT": (-8.6529, 117.3616),
    "NUSA TENGGARA TIMUR": (-8.6574, 121.0794),
    "KALIMANTAN BARAT": (-0.2788, 111.4753),
    "KALIMANTAN TENGAH": (-1.6815, 113.3823),
    "KALIMANTAN SELATAN": (-3.0926, 115.2838),
    "KALIMANTAN TIMUR": (0.5387, 116.4194),
    "KALIMANTAN UTARA": (3.0731, 116.0414),
    "SULAWESI UTARA": (1.4931, 124.8413),
    "SULAWESI TENGAH": (-1.4300, 121.4456),
    "SULAWESI SELATAN": (-3.6688, 119.9741),
    "SULAWESI TENGGARA": (-4.1449, 122.1746),
    "GORONTALO": (0.6999, 122.4467),
    "SULAWESI BARAT": (-2.8441, 119.2321),
    "MALUKU": (-3.2385, 130.1453),
    "MALUKU UTARA": (1.5700, 127.8088),
    "PAPUA BARAT": (-1.3361, 133.1747),
    "PAPUA": (-4.2699, 138.0804),
}


@dataclass(frozen=True)
class DashboardPaths:
    project_root: Path
    combined_input: Path
    national_input: Path
    category_input: Path
    deficit_input: Path
    surplus_input: Path
    phase3h_metadata_input: Path
    output_dir: Path
    kpi_yearly_csv: Path
    kpi_latest_csv: Path
    national_timeseries_csv: Path
    category_summary_csv: Path
    category_summary_all_years_csv: Path
    map_province_csv: Path
    map_province_enriched_csv: Path
    ranking_deficit_csv: Path
    ranking_surplus_csv: Path
    province_detail_csv: Path
    province_latest_csv: Path
    model_summary_csv: Path
    data_quality_summary_csv: Path
    data_quality_by_province_csv: Path
    attention_list_csv: Path
    metadata_csv: Path
    metadata_v2_csv: Path
    source_registry_json: Path
    quality_checks_csv: Path
    report_markdown: Path


def discover_project_root() -> Path:
    env_root = os.getenv("ECADIN_PROJECT_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()

    current = Path(__file__).resolve()
    for candidate in [current.parent, *current.parents]:
        if (candidate / "outputs").exists() and (candidate / "src").exists():
            return candidate
    return Path.cwd().resolve()


def resolve_path(root: Path, supplied: Optional[str | Path], default_relative: str) -> Path:
    path = Path(supplied) if supplied is not None else Path(default_relative)
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def resolve_paths(
    *,
    project_root: Optional[str | Path] = None,
    combined_input: Optional[str | Path] = None,
    national_input: Optional[str | Path] = None,
    category_input: Optional[str | Path] = None,
    deficit_input: Optional[str | Path] = None,
    surplus_input: Optional[str | Path] = None,
    phase3h_metadata_input: Optional[str | Path] = None,
    output_dir: Optional[str | Path] = None,
) -> DashboardPaths:
    root = (
        Path(project_root).expanduser().resolve()
        if project_root is not None
        else discover_project_root()
    )
    source_dir = Path("outputs/gap/phase3h_combined_v1")
    out_dir = resolve_path(
        root,
        output_dir,
        "outputs/dashboard/phase3i_harmonized_v1",
    )

    return DashboardPaths(
        project_root=root,
        combined_input=resolve_path(
            root,
            combined_input,
            str(source_dir / "supply_demand_gap_combined_v1_2011_2030.csv"),
        ),
        national_input=resolve_path(
            root,
            national_input,
            str(source_dir / "supply_demand_gap_combined_v1_national_2011_2030.csv"),
        ),
        category_input=resolve_path(
            root,
            category_input,
            str(source_dir / "supply_demand_gap_combined_v1_category_summary_2011_2030.csv"),
        ),
        deficit_input=resolve_path(
            root,
            deficit_input,
            str(source_dir / "supply_demand_gap_combined_v1_ranking_deficit_2025_2030.csv"),
        ),
        surplus_input=resolve_path(
            root,
            surplus_input,
            str(source_dir / "supply_demand_gap_combined_v1_ranking_surplus_2025_2030.csv"),
        ),
        phase3h_metadata_input=resolve_path(
            root,
            phase3h_metadata_input,
            str(source_dir / "supply_demand_gap_combined_v1_metadata.json"),
        ),
        output_dir=out_dir,
        kpi_yearly_csv=out_dir / "dashboard_kpi_yearly.csv",
        kpi_latest_csv=out_dir / "dashboard_kpi_latest.csv",
        national_timeseries_csv=out_dir / "dashboard_national_timeseries.csv",
        category_summary_csv=out_dir / "dashboard_category_summary.csv",
        category_summary_all_years_csv=out_dir / "dashboard_category_summary_all_years.csv",
        map_province_csv=out_dir / "dashboard_map_province.csv",
        map_province_enriched_csv=out_dir / "dashboard_map_province_enriched.csv",
        ranking_deficit_csv=out_dir / "dashboard_ranking_deficit.csv",
        ranking_surplus_csv=out_dir / "dashboard_ranking_surplus.csv",
        province_detail_csv=out_dir / "dashboard_province_detail.csv",
        province_latest_csv=out_dir / "dashboard_province_latest.csv",
        model_summary_csv=out_dir / "dashboard_model_summary.csv",
        data_quality_summary_csv=out_dir / "dashboard_data_quality_summary.csv",
        data_quality_by_province_csv=out_dir / "dashboard_data_quality_by_province.csv",
        attention_list_csv=out_dir / "dashboard_attention_list.csv",
        metadata_csv=out_dir / "dashboard_metadata.csv",
        metadata_v2_csv=out_dir / "dashboard_metadata_v2.csv",
        source_registry_json=out_dir / "dashboard_source_registry.json",
        quality_checks_csv=out_dir / "dashboard_harmonized_v1_quality_checks.csv",
        report_markdown=out_dir / "PHASE3I_HARMONIZED_DASHBOARD_STAGING.md",
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"{label} tidak ditemukan: {path}")


def normalize_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False).astype(bool)
    return (
        series.astype("string")
        .str.strip()
        .str.lower()
        .map(
            {
                "true": True,
                "false": False,
                "1": True,
                "0": False,
                "yes": True,
                "no": False,
                "ya": True,
                "tidak": False,
            }
        )
        .fillna(False)
        .astype(bool)
    )


def read_csv(path: Path, label: str) -> pd.DataFrame:
    require_file(path, label)
    return pd.read_csv(path, low_memory=False)


def load_inputs(paths: DashboardPaths) -> dict[str, object]:
    combined = read_csv(paths.combined_input, "Phase 3H combined gap")
    national = read_csv(paths.national_input, "Phase 3H national gap")
    category = read_csv(paths.category_input, "Phase 3H category summary")
    deficit = read_csv(paths.deficit_input, "Phase 3H deficit ranking")
    surplus = read_csv(paths.surplus_input, "Phase 3H surplus ranking")
    require_file(paths.phase3h_metadata_input, "Phase 3H metadata")
    metadata = json.loads(paths.phase3h_metadata_input.read_text(encoding="utf-8"))

    for frame in [combined, national, category, deficit, surplus]:
        if "tahun" in frame.columns:
            frame["tahun"] = pd.to_numeric(frame["tahun"], errors="raise").astype(int)

    for column in [
        "demand_available",
        "supply_available",
        "gap_available",
        "demand_is_observed",
        "supply_is_observed",
        "demand_is_interpolated",
        "supply_is_interpolated",
    ]:
        if column in combined.columns:
            combined[column] = normalize_bool(combined[column])

    return {
        "combined": combined,
        "national": national,
        "category": category,
        "deficit": deficit,
        "surplus": surplus,
        "phase3h_metadata": metadata,
    }


def classify_gap_color(gap: pd.Series, available: pd.Series) -> pd.Series:
    result = np.select(
        [gap.gt(0), gap.lt(0)],
        ["Surplus", "Defisit"],
        default="Seimbang",
    )
    result = pd.Series(result, index=gap.index, dtype="object")
    result.loc[~available] = "Tidak Tersedia"
    return result


def build_kpi_yearly(national: pd.DataFrame, combined: pd.DataFrame) -> pd.DataFrame:
    counts = (
        combined.groupby(["tahun", "data_type", "gap_category"], dropna=False)
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )

    for column in [
        "defisit_tinggi",
        "defisit_moderat",
        "relatif_seimbang",
        "surplus_moderat",
        "surplus_tinggi",
        "tidak_tersedia",
    ]:
        if column not in counts.columns:
            counts[column] = 0

    counts["jumlah_defisit_total"] = (
        counts["defisit_tinggi"] + counts["defisit_moderat"]
    )
    counts["jumlah_relatif_seimbang"] = counts["relatif_seimbang"]
    counts["jumlah_surplus_total"] = (
        counts["surplus_moderat"] + counts["surplus_tinggi"]
    )
    counts = counts.rename(
        columns={
            "tidak_tersedia": "jumlah_tidak_tersedia",
            "defisit_tinggi": "jumlah_defisit_tinggi",
            "defisit_moderat": "jumlah_defisit_moderat",
            "surplus_moderat": "jumlah_surplus_moderat",
            "surplus_tinggi": "jumlah_surplus_tinggi",
        }
    )

    kpi = national.copy()
    kpi["total_demand_gwh"] = kpi["total_demand_overlap_gwh"]
    kpi["total_supply_gwh"] = kpi["total_supply_overlap_gwh"]
    kpi["total_gap_gwh"] = kpi["total_gap_supply_minus_demand_gwh"]
    kpi = kpi.merge(
        counts[
            [
                "tahun",
                "data_type",
                "jumlah_defisit_tinggi",
                "jumlah_defisit_moderat",
                "jumlah_defisit_total",
                "jumlah_relatif_seimbang",
                "jumlah_surplus_moderat",
                "jumlah_surplus_tinggi",
                "jumlah_surplus_total",
                "jumlah_tidak_tersedia",
            ]
        ],
        on=["tahun", "data_type"],
        how="left",
        validate="one_to_one",
    )

    columns = [
        "tahun",
        "data_type",
        "scenario",
        "geography",
        "total_demand_gwh",
        "total_supply_gwh",
        "total_gap_gwh",
        "supply_to_demand_ratio",
        "gap_to_demand_percent",
        "jumlah_wilayah",
        "jumlah_wilayah_gap_lengkap",
        "jumlah_defisit_tinggi",
        "jumlah_defisit_moderat",
        "jumlah_defisit_total",
        "jumlah_relatif_seimbang",
        "jumlah_surplus_moderat",
        "jumlah_surplus_tinggi",
        "jumlah_surplus_total",
        "jumlah_tidak_tersedia",
        "data_completeness",
        "demand_growth_yoy_percent",
        "supply_growth_yoy_percent",
    ]
    return kpi[columns].sort_values("tahun").reset_index(drop=True)


def build_national_timeseries(national: pd.DataFrame) -> pd.DataFrame:
    output = national.copy()
    output["total_demand_gwh"] = output["total_demand_overlap_gwh"]
    output["total_supply_gwh"] = output["total_supply_overlap_gwh"]
    output["gap_supply_minus_demand_gwh"] = (
        output["total_gap_supply_minus_demand_gwh"]
    )
    columns = [
        "tahun",
        "data_type",
        "scenario",
        "geography",
        "total_demand_gwh",
        "total_supply_gwh",
        "gap_supply_minus_demand_gwh",
        "supply_to_demand_ratio",
        "gap_to_demand_percent",
        "jumlah_wilayah",
        "jumlah_wilayah_gap_lengkap",
        "data_completeness",
        "demand_growth_yoy_percent",
        "supply_growth_yoy_percent",
    ]
    return output[columns].sort_values("tahun").reset_index(drop=True)


def build_province_detail(combined: pd.DataFrame) -> pd.DataFrame:
    detail = combined.copy()
    coordinates = detail["provinsi"].map(COORDINATES)
    detail["latitude"] = coordinates.map(
        lambda value: value[0] if isinstance(value, tuple) else np.nan
    )
    detail["longitude"] = coordinates.map(
        lambda value: value[1] if isinstance(value, tuple) else np.nan
    )
    detail["map_color_group"] = classify_gap_color(
        detail["gap_supply_minus_demand_gwh"],
        detail["gap_available"],
    )
    detail["bubble_size"] = np.where(
        detail["gap_available"],
        np.sqrt(detail["gap_abs_gwh"].clip(lower=0)) * 3.0,
        0.0,
    )
    detail["bubble_size_gap"] = detail["bubble_size"]
    detail["bubble_size_demand"] = np.where(
        detail["demand_available"],
        np.sqrt(detail["demand_gwh"].clip(lower=0)) * 2.0,
        0.0,
    )
    detail["bubble_size_supply"] = np.where(
        detail["supply_available"],
        np.sqrt(detail["supply_gwh"].clip(lower=0)) * 2.0,
        0.0,
    )

    detail["data_quality_badge"] = np.select(
        [
            detail["gap_available"]
            & detail["demand_is_observed"]
            & detail["supply_is_observed"],
            detail["gap_available"]
            & (
                detail["demand_is_interpolated"]
                | detail["supply_is_interpolated"]
            ),
            detail["gap_available"],
        ],
        [
            "observed_complete",
            "includes_interpolation",
            "available_other",
        ],
        default="incomplete",
    )

    detail["attention_flag"] = (
        ~detail["gap_available"]
        | detail["gap_category"].isin(["defisit_tinggi"])
        | (
            detail["data_type"].eq("forecast")
            & detail["gap_to_demand_percent"].abs().ge(50)
        )
    )
    detail["attention_reason"] = np.select(
        [
            ~detail["gap_available"],
            detail["gap_category"].eq("defisit_tinggi"),
            detail["data_type"].eq("forecast")
            & detail["gap_to_demand_percent"].ge(50),
        ],
        [
            "gap_tidak_lengkap",
            "defisit_tinggi",
            "surplus_tinggi_perlu_interpretasi_interkoneksi",
        ],
        default="",
    )
    detail["regional_uncertainty_display_allowed"] = (
        REGIONAL_UNCERTAINTY_DISPLAY_ALLOWED
    )

    # Do not export regional uncertainty values to dashboard staging.
    detail = detail.drop(
        columns=[
            "supply_lower_80_gwh",
            "supply_upper_80_gwh",
            "supply_lower_95_gwh",
            "supply_upper_95_gwh",
            "uncertainty_size_bucket",
            "uncertainty_calibration_source",
        ],
        errors="ignore",
    )

    return detail.sort_values(["tahun", "provinsi"]).reset_index(drop=True)


def build_map(detail: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    base_columns = [
        "tahun",
        "provinsi",
        "data_type",
        "scenario",
        "geography",
        "demand_gwh",
        "supply_gwh",
        "gap_supply_minus_demand_gwh",
        "gap_abs_gwh",
        "supply_to_demand_ratio",
        "gap_to_demand_percent",
        "gap_category",
        "demand_available",
        "supply_available",
        "gap_available",
        "latitude",
        "longitude",
        "bubble_size",
        "map_color_group",
        "data_quality_badge",
        "attention_flag",
    ]
    map_base = detail[base_columns].copy()

    enriched_columns = [
        *base_columns,
        "bubble_size_gap",
        "bubble_size_demand",
        "bubble_size_supply",
        "demand_value_status",
        "supply_value_status",
        "demand_is_observed",
        "supply_is_observed",
        "demand_is_interpolated",
        "supply_is_interpolated",
        "demand_model_name",
        "supply_model_name",
        "demand_model_version",
        "supply_model_version",
        "attention_reason",
        "regional_uncertainty_display_allowed",
    ]
    enriched_columns = [column for column in enriched_columns if column in detail.columns]
    map_enriched = detail[enriched_columns].copy()
    return map_base, map_enriched


def build_rankings(deficit: pd.DataFrame, surplus: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    columns = [
        "tahun",
        "provinsi",
        "data_type",
        "demand_gwh",
        "supply_gwh",
        "gap_supply_minus_demand_gwh",
        "gap_abs_gwh",
        "supply_to_demand_ratio",
        "gap_to_demand_percent",
        "gap_category",
        "gap_available",
        "demand_model_name",
        "supply_model_name",
    ]

    deficit_columns = [column for column in columns if column in deficit.columns]
    surplus_columns = [column for column in columns if column in surplus.columns]
    deficit_out = deficit[deficit_columns + ["rank_deficit"]].copy()
    surplus_out = surplus[surplus_columns + ["rank_surplus"]].copy()
    return (
        deficit_out.sort_values(["tahun", "rank_deficit", "provinsi"]).reset_index(drop=True),
        surplus_out.sort_values(["tahun", "rank_surplus", "provinsi"]).reset_index(drop=True),
    )


def build_category_summaries(category: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    all_years = category.rename(columns={"jumlah_wilayah": "jumlah_provinsi"}).copy()
    forecast = all_years.loc[all_years["tahun"].isin(FORECAST_YEARS)].copy()
    return (
        forecast.sort_values(["tahun", "gap_category"]).reset_index(drop=True),
        all_years.sort_values(["tahun", "gap_category"]).reset_index(drop=True),
    )


def build_model_summary() -> pd.DataFrame:
    rows = [
        {
            "side": "demand",
            "active_model": "drift",
            "model_version": "demand_production_drift",
            "status": "production",
            "forecast_period": "2025-2030",
            "geography": "34_harmonized_modeling_regions",
            "selection_basis": "validated production contract",
            "legacy_model_reused": False,
            "regional_uncertainty_display_allowed": False,
            "note": "Demand forecast consumed from the validated Phase 3G/3H contract.",
        },
        {
            "side": "supply",
            "active_model": "drift",
            "model_version": "supply_production_drift_v1",
            "status": "production",
            "forecast_period": "2025-2030",
            "geography": "34_harmonized_modeling_regions",
            "selection_basis": "nested robustness validation",
            "legacy_model_reused": False,
            "regional_uncertainty_display_allowed": False,
            "note": "Legacy Ridge is archived and is not used by this dashboard staging dataset.",
        },
    ]
    return pd.DataFrame(rows)


def build_quality_outputs(
    detail: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    quality_summary = (
        detail.groupby(["tahun", "data_type", "data_quality_badge"], dropna=False)
        .size()
        .reset_index(name="jumlah_wilayah")
        .sort_values(["tahun", "data_type", "data_quality_badge"])
        .reset_index(drop=True)
    )
    quality_by_province = (
        detail.groupby(["provinsi", "data_quality_badge"], dropna=False)
        .size()
        .reset_index(name="jumlah_tahun")
        .sort_values(["provinsi", "data_quality_badge"])
        .reset_index(drop=True)
    )
    attention_columns = [
        "tahun",
        "provinsi",
        "data_type",
        "demand_gwh",
        "supply_gwh",
        "gap_supply_minus_demand_gwh",
        "gap_to_demand_percent",
        "gap_category",
        "data_quality_badge",
        "attention_reason",
    ]
    attention = (
        detail.loc[detail["attention_flag"], attention_columns]
        .sort_values(
            ["data_type", "tahun", "gap_supply_minus_demand_gwh", "provinsi"],
            ascending=[True, True, True, True],
        )
        .reset_index(drop=True)
    )
    return quality_summary, quality_by_province, attention


def build_metadata_frames(
    *,
    detail: pd.DataFrame,
    phase3h_metadata: dict[str, object],
    source_registry: dict[str, object],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    metadata_rows = [
        {
            "bagian": "Cakupan",
            "penjelasan": "Dashboard menggunakan 34 wilayah modeling harmonisasi untuk periode 2011-2030.",
        },
        {
            "bagian": "Historis",
            "penjelasan": "Periode 2011-2024 menggunakan target_training_gwh dari panel harmonisasi; 9 gap historis yang tidak tersedia tetap kosong.",
        },
        {
            "bagian": "Forecast",
            "penjelasan": "Periode 2025-2030 menggunakan forecast produksi Drift untuk demand dan supply.",
        },
        {
            "bagian": "Model Demand",
            "penjelasan": "Model produksi demand yang ditampilkan adalah Drift.",
        },
        {
            "bagian": "Model Supply",
            "penjelasan": "Model produksi supply adalah Drift V1; Ridge telah diarsipkan dan tidak digunakan.",
        },
        {
            "bagian": "Interpretasi Gap",
            "penjelasan": "Gap regional adalah proxy perencanaan; aliran listrik dan interkoneksi lintas wilayah harus dipertimbangkan.",
        },
        {
            "bagian": "Ketidakpastian",
            "penjelasan": "Interval ketidakpastian supply regional belum ditampilkan karena kalibrasi wilayah kecil masih bersifat eksperimen.",
        },
        {
            "bagian": "Kelengkapan Data",
            "penjelasan": "Tahun 2011, 2012, 2013, 2014, dan 2020 memiliki partial historical coverage.",
        },
        {
            "bagian": "Status",
            "penjelasan": "Dataset ini adalah staging dashboard Phase 3I dan belum menimpa output dashboard canonical.",
        },
    ]
    metadata = pd.DataFrame(metadata_rows)

    metadata_v2 = pd.DataFrame(
        [
            {"key": "stage_version", "value": STAGE_VERSION},
            {"key": "schema_version", "value": SCHEMA_VERSION},
            {"key": "period", "value": "2011-2030"},
            {"key": "region_count", "value": EXPECTED_REGION_COUNT},
            {"key": "row_count", "value": len(detail)},
            {"key": "complete_gap_count", "value": int(detail["gap_available"].sum())},
            {"key": "historical_incomplete_gap_count", "value": int((~detail["gap_available"] & detail["data_type"].eq("historical")).sum())},
            {"key": "forecast_complete_gap_count", "value": int((detail["gap_available"] & detail["data_type"].eq("forecast")).sum())},
            {"key": "active_demand_model", "value": "drift"},
            {"key": "active_supply_model", "value": "drift"},
            {"key": "active_supply_version", "value": "supply_production_drift_v1"},
            {"key": "geography", "value": "34_harmonized_modeling_regions"},
            {"key": "regional_uncertainty_display_allowed", "value": False},
            {"key": "phase3h_ready", "value": phase3h_metadata.get("ready_for_dashboard_integration")},
            {"key": "dashboard_status", "value": "staging_validated_not_promoted"},
            {"key": "source_registry_status", "value": source_registry["status"]},
        ]
    )
    return metadata, metadata_v2


def run_quality_checks(
    *,
    paths: DashboardPaths,
    combined: pd.DataFrame,
    national: pd.DataFrame,
    phase3h_metadata: dict[str, object],
    kpi_yearly: pd.DataFrame,
    national_timeseries: pd.DataFrame,
    category_forecast: pd.DataFrame,
    map_base: pd.DataFrame,
    map_enriched: pd.DataFrame,
    deficit: pd.DataFrame,
    surplus: pd.DataFrame,
    detail: pd.DataFrame,
    latest: pd.DataFrame,
    model_summary: pd.DataFrame,
) -> pd.DataFrame:
    checks: list[dict[str, object]] = []

    def add(
        name: str,
        passed: bool,
        observed: object,
        expected: object,
        severity: str = "error",
    ) -> None:
        checks.append(
            {
                "check": name,
                "passed": bool(passed),
                "severity": severity,
                "observed": str(observed),
                "expected": str(expected),
            }
        )

    add("phase3h_ready", phase3h_metadata.get("ready_for_dashboard_integration") is True, phase3h_metadata.get("ready_for_dashboard_integration"), True)
    add("phase3h_critical_failures", phase3h_metadata.get("critical_failure_count") == 0, phase3h_metadata.get("critical_failure_count"), 0)
    add("combined_input_hash", phase3h_metadata.get("combined_row_count") == len(combined), len(combined), phase3h_metadata.get("combined_row_count"))
    add("combined_rows", len(combined) == EXPECTED_COMBINED_ROWS, len(combined), EXPECTED_COMBINED_ROWS)
    add("combined_regions", combined["provinsi"].nunique() == EXPECTED_REGION_COUNT, int(combined["provinsi"].nunique()), EXPECTED_REGION_COUNT)
    add("combined_years", sorted(combined["tahun"].unique().tolist()) == EXPECTED_YEARS, sorted(combined["tahun"].unique().tolist()), EXPECTED_YEARS)
    add("combined_no_duplicates", not combined.duplicated(["tahun", "provinsi"]).any(), int(combined.duplicated(["tahun", "provinsi"]).sum()), 0)
    add("historical_rows", int(combined["data_type"].eq("historical").sum()) == EXPECTED_HISTORICAL_ROWS, int(combined["data_type"].eq("historical").sum()), EXPECTED_HISTORICAL_ROWS)
    add("forecast_rows", int(combined["data_type"].eq("forecast").sum()) == EXPECTED_FORECAST_ROWS, int(combined["data_type"].eq("forecast").sum()), EXPECTED_FORECAST_ROWS)
    add("complete_rows", int(combined["gap_available"].sum()) == EXPECTED_COMPLETE_ROWS, int(combined["gap_available"].sum()), EXPECTED_COMPLETE_ROWS)
    add("historical_incomplete_rows", int((combined["data_type"].eq("historical") & ~combined["gap_available"]).sum()) == EXPECTED_INCOMPLETE_HISTORICAL_ROWS, int((combined["data_type"].eq("historical") & ~combined["gap_available"]).sum()), EXPECTED_INCOMPLETE_HISTORICAL_ROWS)
    add("forecast_all_complete", combined.loc[combined["data_type"].eq("forecast"), "gap_available"].all(), int(combined.loc[combined["data_type"].eq("forecast"), "gap_available"].sum()), EXPECTED_FORECAST_ROWS)
    add("forecast_models_drift_demand", combined.loc[combined["data_type"].eq("forecast"), "demand_model_name"].astype(str).str.lower().eq("drift").all(), sorted(combined.loc[combined["data_type"].eq("forecast"), "demand_model_name"].astype(str).str.lower().unique().tolist()), ["drift"])
    add("forecast_models_drift_supply", combined.loc[combined["data_type"].eq("forecast"), "supply_model_name"].astype(str).str.lower().eq("drift").all(), sorted(combined.loc[combined["data_type"].eq("forecast"), "supply_model_name"].astype(str).str.lower().unique().tolist()), ["drift"])
    add("national_rows", len(national) == 20, len(national), 20)
    add("kpi_yearly_rows", len(kpi_yearly) == 20, len(kpi_yearly), 20)
    add("national_timeseries_rows", len(national_timeseries) == 20, len(national_timeseries), 20)
    add("category_forecast_years", sorted(category_forecast["tahun"].unique().tolist()) == FORECAST_YEARS, sorted(category_forecast["tahun"].unique().tolist()), FORECAST_YEARS)
    add("map_base_rows", len(map_base) == EXPECTED_COMBINED_ROWS, len(map_base), EXPECTED_COMBINED_ROWS)
    add("map_enriched_rows", len(map_enriched) == EXPECTED_COMBINED_ROWS, len(map_enriched), EXPECTED_COMBINED_ROWS)
    add("map_coordinates_complete", map_base[["latitude", "longitude"]].notna().all().all(), map_base.loc[map_base[["latitude", "longitude"]].isna().any(axis=1), "provinsi"].drop_duplicates().tolist(), [])
    add("ranking_deficit_rows", len(deficit) == EXPECTED_FORECAST_ROWS, len(deficit), EXPECTED_FORECAST_ROWS)
    add("ranking_surplus_rows", len(surplus) == EXPECTED_FORECAST_ROWS, len(surplus), EXPECTED_FORECAST_ROWS)
    add("province_detail_rows", len(detail) == EXPECTED_COMBINED_ROWS, len(detail), EXPECTED_COMBINED_ROWS)
    add("province_latest_rows", len(latest) == EXPECTED_REGION_COUNT, len(latest), EXPECTED_REGION_COUNT)
    add("province_latest_year", latest["tahun"].eq(2030).all(), sorted(latest["tahun"].unique().tolist()), [2030])
    add("model_summary_rows", len(model_summary) == 2, len(model_summary), 2)
    add(
        "model_summary_active_models_drift",
        model_summary["active_model"].astype(str).str.lower().eq("drift").all(),
        sorted(model_summary["active_model"].astype(str).str.lower().unique().tolist()),
        ["drift"],
    )
    add(
        "model_summary_legacy_not_reused",
        normalize_bool(model_summary["legacy_model_reused"]).eq(False).all(),
        sorted(normalize_bool(model_summary["legacy_model_reused"]).unique().tolist()),
        [False],
    )
    add("regional_uncertainty_hidden_detail", not any(column.startswith("supply_lower_") or column.startswith("supply_upper_") for column in detail.columns), [column for column in detail.columns if column.startswith("supply_lower_") or column.startswith("supply_upper_")], [])
    add("regional_uncertainty_flag_false", detail["regional_uncertainty_display_allowed"].eq(False).all(), sorted(detail["regional_uncertainty_display_allowed"].unique().tolist()), [False])
    add("canonical_dashboard_not_overwritten", paths.output_dir.name == "phase3i_harmonized_v1", str(paths.output_dir), "outputs/dashboard/phase3i_harmonized_v1")

    return pd.DataFrame(checks)


def validate_or_raise(checks: pd.DataFrame) -> None:
    failed = checks.loc[~checks["passed"] & checks["severity"].eq("error")]
    if not failed.empty:
        raise ValueError(
            "Phase 3I quality checks gagal:\n"
            + failed.to_string(index=False)
        )


def build_source_registry(
    paths: DashboardPaths,
    phase3h_metadata: dict[str, object],
) -> dict[str, object]:
    return {
        "dashboard_stage_version": STAGE_VERSION,
        "status": "staging_validated_not_promoted",
        "source_contract": {
            "name": "supply_demand_gap_combined_v1",
            "period": [2011, 2030],
            "geography": "34_harmonized_modeling_regions",
            "combined_file": str(paths.combined_input),
            "combined_sha256": sha256_file(paths.combined_input),
            "national_file": str(paths.national_input),
            "national_sha256": sha256_file(paths.national_input),
            "phase3h_metadata_file": str(paths.phase3h_metadata_input),
            "phase3h_metadata_sha256": sha256_file(paths.phase3h_metadata_input),
            "phase3h_ready_for_dashboard": phase3h_metadata.get(
                "ready_for_dashboard_integration"
            ),
        },
        "active_models": {
            "demand": {
                "name": "drift",
                "status": "production",
            },
            "supply": {
                "name": "drift",
                "version": "supply_production_drift_v1",
                "status": "production",
            },
        },
        "legacy_ridge_used": False,
        "regional_uncertainty_display_allowed": False,
        "canonical_dashboard_files_modified": False,
    }


def build_report(
    *,
    paths: DashboardPaths,
    detail: pd.DataFrame,
    checks: pd.DataFrame,
    attention: pd.DataFrame,
) -> str:
    historical_incomplete = detail.loc[
        detail["data_type"].eq("historical") & ~detail["gap_available"]
    ]
    forecast = detail.loc[detail["data_type"].eq("forecast")]

    lines = [
        "# ECADIN Phase 3I — Harmonized Dashboard Staging V1",
        "",
        f"Combined source: `{paths.combined_input}`",
        f"Output directory: `{paths.output_dir}`",
        "",
        "## Contract",
        "",
        f"- Rows: **{len(detail)}**.",
        f"- Regions: **{detail['provinsi'].nunique()}**.",
        f"- Period: **{detail['tahun'].min()}–{detail['tahun'].max()}**.",
        f"- Historical rows: **{int(detail['data_type'].eq('historical').sum())}**.",
        f"- Forecast rows: **{int(detail['data_type'].eq('forecast').sum())}**.",
        f"- Complete forecast rows: **{int(forecast['gap_available'].sum())}**.",
        f"- Retained historical incomplete rows: **{len(historical_incomplete)}**.",
        f"- Critical failures: **{int((~checks['passed'] & checks['severity'].eq('error')).sum())}**.",
        "",
        "## Production model status",
        "",
        "- Demand production model: **Drift**.",
        "- Supply production model: **Drift V1**.",
        "- Legacy Ridge used: **No**.",
        "- Regional uncertainty displayed: **No**.",
        "",
        "## Dashboard compatibility",
        "",
        "- Streamlit-compatible filenames are produced in a versioned staging folder.",
        "- `dashboard_map_province.csv` contains 680 harmonized region-year rows.",
        "- Forecast ranking files contain 204 rows each.",
        "- Forecast category summary remains restricted to 2025–2030 for existing chart compatibility.",
        "",
        "## Historical incomplete rows",
        "",
        "| Year | Region | Demand status | Supply status |",
        "|---:|---|---|---|",
    ]
    for _, row in historical_incomplete.iterrows():
        lines.append(
            f"| {int(row['tahun'])} | {row['provinsi']} | "
            f"{row['demand_value_status']} | {row['supply_value_status']} |"
        )

    lines += [
        "",
        "## Attention list",
        "",
        f"- Attention rows: **{len(attention)}**.",
        "- Attention includes incomplete gaps, high deficits, and extreme forecast surpluses that require interconnection-aware interpretation.",
        "",
        "## Promotion status",
        "",
        "This stage does not overwrite `outputs/dashboard/dashboard_*.csv`. "
        "Canonical promotion and replacement of the legacy orchestration runner "
        "must occur only after the independent Phase 3I validator passes.",
    ]
    return "\n".join(lines) + "\n"


def export_outputs(
    *,
    paths: DashboardPaths,
    outputs: dict[str, pd.DataFrame],
    source_registry: dict[str, object],
    checks: pd.DataFrame,
    report: str,
) -> None:
    paths.output_dir.mkdir(parents=True, exist_ok=True)

    mapping = {
        "kpi_yearly": paths.kpi_yearly_csv,
        "kpi_latest": paths.kpi_latest_csv,
        "national_timeseries": paths.national_timeseries_csv,
        "category_forecast": paths.category_summary_csv,
        "category_all_years": paths.category_summary_all_years_csv,
        "map_base": paths.map_province_csv,
        "map_enriched": paths.map_province_enriched_csv,
        "ranking_deficit": paths.ranking_deficit_csv,
        "ranking_surplus": paths.ranking_surplus_csv,
        "province_detail": paths.province_detail_csv,
        "province_latest": paths.province_latest_csv,
        "model_summary": paths.model_summary_csv,
        "quality_summary": paths.data_quality_summary_csv,
        "quality_by_province": paths.data_quality_by_province_csv,
        "attention": paths.attention_list_csv,
        "metadata": paths.metadata_csv,
        "metadata_v2": paths.metadata_v2_csv,
    }
    for key, path in mapping.items():
        outputs[key].to_csv(path, index=False, encoding="utf-8-sig")

    paths.source_registry_json.write_text(
        json.dumps(source_registry, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    checks.to_csv(paths.quality_checks_csv, index=False, encoding="utf-8-sig")
    paths.report_markdown.write_text(report, encoding="utf-8")


def run_phase3i(
    *,
    project_root: Optional[str | Path] = None,
    combined_input: Optional[str | Path] = None,
    national_input: Optional[str | Path] = None,
    category_input: Optional[str | Path] = None,
    deficit_input: Optional[str | Path] = None,
    surplus_input: Optional[str | Path] = None,
    phase3h_metadata_input: Optional[str | Path] = None,
    output_dir: Optional[str | Path] = None,
    dry_run: bool = False,
) -> dict[str, object]:
    paths = resolve_paths(
        project_root=project_root,
        combined_input=combined_input,
        national_input=national_input,
        category_input=category_input,
        deficit_input=deficit_input,
        surplus_input=surplus_input,
        phase3h_metadata_input=phase3h_metadata_input,
        output_dir=output_dir,
    )
    inputs = load_inputs(paths)
    combined = inputs["combined"]
    national = inputs["national"]
    category = inputs["category"]
    deficit_source = inputs["deficit"]
    surplus_source = inputs["surplus"]
    phase3h_metadata = inputs["phase3h_metadata"]

    kpi_yearly = build_kpi_yearly(national, combined)
    kpi_latest = kpi_yearly.loc[kpi_yearly["tahun"].eq(2030)].copy()
    national_timeseries = build_national_timeseries(national)
    province_detail = build_province_detail(combined)
    map_base, map_enriched = build_map(province_detail)
    ranking_deficit, ranking_surplus = build_rankings(
        deficit_source,
        surplus_source,
    )
    category_forecast, category_all_years = build_category_summaries(category)
    province_latest = (
        province_detail.loc[province_detail["tahun"].eq(2030)]
        .sort_values(
            ["gap_available", "gap_supply_minus_demand_gwh", "provinsi"],
            ascending=[False, True, True],
        )
        .reset_index(drop=True)
    )
    model_summary = build_model_summary()
    quality_summary, quality_by_province, attention = build_quality_outputs(
        province_detail
    )
    source_registry = build_source_registry(paths, phase3h_metadata)
    metadata, metadata_v2 = build_metadata_frames(
        detail=province_detail,
        phase3h_metadata=phase3h_metadata,
        source_registry=source_registry,
    )

    checks = run_quality_checks(
        paths=paths,
        combined=combined,
        national=national,
        phase3h_metadata=phase3h_metadata,
        kpi_yearly=kpi_yearly,
        national_timeseries=national_timeseries,
        category_forecast=category_forecast,
        map_base=map_base,
        map_enriched=map_enriched,
        deficit=ranking_deficit,
        surplus=ranking_surplus,
        detail=province_detail,
        latest=province_latest,
        model_summary=model_summary,
    )
    validate_or_raise(checks)

    outputs = {
        "kpi_yearly": kpi_yearly,
        "kpi_latest": kpi_latest,
        "national_timeseries": national_timeseries,
        "category_forecast": category_forecast,
        "category_all_years": category_all_years,
        "map_base": map_base,
        "map_enriched": map_enriched,
        "ranking_deficit": ranking_deficit,
        "ranking_surplus": ranking_surplus,
        "province_detail": province_detail,
        "province_latest": province_latest,
        "model_summary": model_summary,
        "quality_summary": quality_summary,
        "quality_by_province": quality_by_province,
        "attention": attention,
        "metadata": metadata,
        "metadata_v2": metadata_v2,
    }
    report = build_report(
        paths=paths,
        detail=province_detail,
        checks=checks,
        attention=attention,
    )

    critical_failures = int(
        (~checks["passed"] & checks["severity"].eq("error")).sum()
    )

    print("=" * 92)
    print("ECADIN PHASE 3I - HARMONIZED DASHBOARD STAGING")
    print("=" * 92)
    print(f"Combined source          : {paths.combined_input}")
    print(f"National source          : {paths.national_input}")
    print(f"Output directory         : {paths.output_dir}")
    print(f"Dashboard rows           : {len(province_detail)}")
    print(f"Regions                  : {province_detail['provinsi'].nunique()}")
    print(f"Years                    : {province_detail['tahun'].min()}-{province_detail['tahun'].max()}")
    print(f"Complete forecast rows   : {int((province_detail['data_type'].eq('forecast') & province_detail['gap_available']).sum())}")
    print(f"Historical missing rows  : {int((province_detail['data_type'].eq('historical') & ~province_detail['gap_available']).sum())}")
    print(f"Regional uncertainty     : hidden")
    print(f"Legacy Ridge used        : False")
    print(f"Critical failures        : {critical_failures}")
    print(f"Ready for promotion      : {critical_failures == 0}")

    print("\nOUTPUT SHAPES")
    print("-" * 92)
    for key, frame in outputs.items():
        print(f"{key:28s}: {frame.shape}")

    if dry_run:
        print("\n[DRY RUN] Validasi lulus. Output staging belum ditulis.")
    else:
        export_outputs(
            paths=paths,
            outputs=outputs,
            source_registry=source_registry,
            checks=checks,
            report=report,
        )
        print("\nOUTPUT FILES")
        print("-" * 92)
        for key, value in asdict(paths).items():
            if key.endswith(("_csv", "_json", "_markdown")):
                print(f"{key:32s}: {value}")
        print("\n[DONE] Phase 3I dashboard staging selesai.")

    return {
        "paths": paths,
        "inputs": inputs,
        "outputs": outputs,
        "source_registry": source_registry,
        "quality_checks": checks,
        "report": report,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build ECADIN Phase 3I harmonized dashboard staging."
    )
    parser.add_argument("--project-root", type=Path, default=None)
    parser.add_argument("--combined-input", type=Path, default=None)
    parser.add_argument("--national-input", type=Path, default=None)
    parser.add_argument("--category-input", type=Path, default=None)
    parser.add_argument("--deficit-input", type=Path, default=None)
    parser.add_argument("--surplus-input", type=Path, default=None)
    parser.add_argument("--phase3h-metadata-input", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    run_phase3i(
        project_root=args.project_root,
        combined_input=args.combined_input,
        national_input=args.national_input,
        category_input=args.category_input,
        deficit_input=args.deficit_input,
        surplus_input=args.surplus_input,
        phase3h_metadata_input=args.phase3h_metadata_input,
        output_dir=args.output_dir,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
