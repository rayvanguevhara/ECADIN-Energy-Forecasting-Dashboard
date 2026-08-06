
"""Build a harmonized 34-region supply-demand gap for ECADIN Phase 3G.

This stage is deliberately versioned and does not overwrite the existing
historical/canonical gap files consumed by the dashboard. It validates the
canonical 2025-2030 demand and supply production forecasts, requires identical
34-region keys, then produces a complete forecast-only gap staging dataset.

Default inputs
--------------
- outputs/models/demand/demand_forecast_2025_2030.csv
- outputs/models/supply/supply_forecast_2025_2030.csv
- outputs/models/supply/supply_model_registry.json

Default output
--------------
outputs/gap/phase3g_harmonized_v1/

The stage is ready for dashboard integration only when all 204 forecast rows
(34 harmonized regions x 6 years) have demand, supply, and a computed gap.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


STAGE_VERSION = "supply_demand_gap_harmonized_v1"
SCHEMA_VERSION = "1.0"
FORECAST_START_YEAR = 2025
FORECAST_END_YEAR = 2030
FORECAST_YEARS = list(range(FORECAST_START_YEAR, FORECAST_END_YEAR + 1))
EXPECTED_REGION_COUNT = 34
EXPECTED_ROW_COUNT = EXPECTED_REGION_COUNT * len(FORECAST_YEARS)

DEMAND_VALUE_COLUMN = "forecast_electricity_distributed_gwh"
SUPPLY_VALUE_COLUMN = "forecast_electricity_generated_gwh"

REQUIRED_DEMAND_COLUMNS = {
    "tahun",
    "provinsi",
    DEMAND_VALUE_COLUMN,
    "model_name",
    "forecast_type",
}
REQUIRED_SUPPLY_COLUMNS = {
    "tahun",
    "provinsi",
    SUPPLY_VALUE_COLUMN,
    "model_name",
    "forecast_type",
}


@dataclass(frozen=True)
class Phase3GPaths:
    project_root: Path
    demand_forecast: Path
    supply_forecast: Path
    supply_registry: Path
    output_dir: Path
    gap_csv: Path
    gap_json: Path
    national_csv: Path
    national_json: Path
    ranking_deficit_csv: Path
    ranking_surplus_csv: Path
    category_summary_csv: Path
    quality_checks_csv: Path
    metadata_json: Path
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


def resolve_path(root: Path, value: Optional[str | Path], default_relative: str) -> Path:
    path = Path(value) if value is not None else Path(default_relative)
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def resolve_paths(
    *,
    project_root: Optional[str | Path] = None,
    demand_forecast: Optional[str | Path] = None,
    supply_forecast: Optional[str | Path] = None,
    supply_registry: Optional[str | Path] = None,
    output_dir: Optional[str | Path] = None,
) -> Phase3GPaths:
    root = (
        Path(project_root).expanduser().resolve()
        if project_root is not None
        else discover_project_root()
    )
    out_dir = resolve_path(
        root,
        output_dir,
        "outputs/gap/phase3g_harmonized_v1",
    )
    prefix = STAGE_VERSION
    return Phase3GPaths(
        project_root=root,
        demand_forecast=resolve_path(
            root,
            demand_forecast,
            "outputs/models/demand/demand_forecast_2025_2030.csv",
        ),
        supply_forecast=resolve_path(
            root,
            supply_forecast,
            "outputs/models/supply/supply_forecast_2025_2030.csv",
        ),
        supply_registry=resolve_path(
            root,
            supply_registry,
            "outputs/models/supply/supply_model_registry.json",
        ),
        output_dir=out_dir,
        gap_csv=out_dir / f"{prefix}_forecast_2025_2030.csv",
        gap_json=out_dir / f"{prefix}_forecast_2025_2030.json",
        national_csv=out_dir / f"{prefix}_national_2025_2030.csv",
        national_json=out_dir / f"{prefix}_national_2025_2030.json",
        ranking_deficit_csv=out_dir / f"{prefix}_ranking_deficit_2025_2030.csv",
        ranking_surplus_csv=out_dir / f"{prefix}_ranking_surplus_2025_2030.csv",
        category_summary_csv=out_dir / f"{prefix}_category_summary_2025_2030.csv",
        quality_checks_csv=out_dir / f"{prefix}_quality_checks.csv",
        metadata_json=out_dir / f"{prefix}_metadata.json",
        report_markdown=out_dir / "PHASE3G_HARMONIZED_SUPPLY_DEMAND_GAP.md",
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_province(value: object) -> str:
    if pd.isna(value):
        return ""
    text = " ".join(str(value).strip().upper().split())
    aliases = {
        "NANGGROE ACEH DARUSSALAM": "ACEH",
        "DKI JAKARTA RAYA": "DKI JAKARTA",
        "D.I. YOGYAKARTA": "DI YOGYAKARTA",
        "D I YOGYAKARTA": "DI YOGYAKARTA",
        "DAERAH ISTIMEWA YOGYAKARTA": "DI YOGYAKARTA",
        "KEP BANGKA BELITUNG": "KEP. BANGKA BELITUNG",
        "KEPULAUAN BANGKA BELITUNG": "KEP. BANGKA BELITUNG",
        "BANGKA BELITUNG": "KEP. BANGKA BELITUNG",
        "KEP RIAU": "KEP. RIAU",
        "KEPULAUAN RIAU": "KEP. RIAU",
        "PAPUA BARATDAYA": "PAPUA BARAT DAYA",
    }
    return aliases.get(text, text)


def require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"{label} tidak ditemukan: {path}")


def load_forecast(path: Path, required_columns: set[str], label: str) -> pd.DataFrame:
    require_file(path, label)
    frame = pd.read_csv(path, low_memory=False)
    missing = sorted(required_columns.difference(frame.columns))
    if missing:
        raise KeyError(f"Kolom wajib {label} tidak ditemukan: {missing}")

    frame = frame.copy()
    frame["tahun"] = pd.to_numeric(frame["tahun"], errors="raise").astype(int)
    frame["provinsi"] = frame["provinsi"].map(normalize_province)
    return frame.sort_values(["tahun", "provinsi"]).reset_index(drop=True)


def load_registry(path: Path) -> dict[str, object]:
    require_file(path, "Supply model registry")
    return json.loads(path.read_text(encoding="utf-8"))


def build_gap(demand: pd.DataFrame, supply: pd.DataFrame) -> pd.DataFrame:
    demand_columns = [
        "tahun",
        "provinsi",
        DEMAND_VALUE_COLUMN,
        "model_name",
        "model_version",
        "forecast_type",
        "forecast_horizon",
        "forecast_growth_yoy_percent",
        "population_projection_jiwa",
        "electrification_ratio_assumption_percent",
    ]
    demand_columns = [column for column in demand_columns if column in demand.columns]
    demand_part = demand[demand_columns].copy().rename(
        columns={
            DEMAND_VALUE_COLUMN: "demand_forecast_gwh",
            "model_name": "demand_model_name",
            "model_version": "demand_model_version",
            "forecast_type": "demand_forecast_type",
            "forecast_horizon": "demand_forecast_horizon",
            "forecast_growth_yoy_percent": "demand_growth_yoy_percent",
        }
    )

    supply_columns = [
        "tahun",
        "provinsi",
        SUPPLY_VALUE_COLUMN,
        "model_name",
        "model_version",
        "forecast_type",
        "forecast_horizon",
        "forecast_growth_yoy_percent",
        "raw_model_prediction_gwh",
        "forecast_adjustment",
        "forecast_lower_80_gwh",
        "forecast_upper_80_gwh",
        "forecast_lower_95_gwh",
        "forecast_upper_95_gwh",
        "uncertainty_size_bucket",
        "uncertainty_calibration_source",
    ]
    supply_columns = [column for column in supply_columns if column in supply.columns]
    supply_part = supply[supply_columns].copy().rename(
        columns={
            SUPPLY_VALUE_COLUMN: "supply_forecast_gwh",
            "model_name": "supply_model_name",
            "model_version": "supply_model_version",
            "forecast_type": "supply_forecast_type",
            "forecast_horizon": "supply_forecast_horizon",
            "forecast_growth_yoy_percent": "supply_growth_yoy_percent",
            "forecast_lower_80_gwh": "supply_lower_80_gwh",
            "forecast_upper_80_gwh": "supply_upper_80_gwh",
            "forecast_lower_95_gwh": "supply_lower_95_gwh",
            "forecast_upper_95_gwh": "supply_upper_95_gwh",
        }
    )

    gap = demand_part.merge(
        supply_part,
        on=["tahun", "provinsi"],
        how="outer",
        validate="one_to_one",
        indicator=True,
    )
    gap["demand_available"] = gap["demand_forecast_gwh"].notna()
    gap["supply_available"] = gap["supply_forecast_gwh"].notna()
    gap["gap_available"] = gap["demand_available"] & gap["supply_available"]
    gap["demand_gwh"] = gap["demand_forecast_gwh"]
    gap["supply_gwh"] = gap["supply_forecast_gwh"]
    gap["gap_supply_minus_demand_gwh"] = gap["supply_gwh"] - gap["demand_gwh"]
    gap["gap_abs_gwh"] = gap["gap_supply_minus_demand_gwh"].abs()
    gap["supply_to_demand_ratio"] = np.where(
        gap["demand_gwh"].gt(0) & gap["supply_gwh"].notna(),
        gap["supply_gwh"] / gap["demand_gwh"],
        np.nan,
    )
    gap["gap_to_demand_percent"] = np.where(
        gap["demand_gwh"].gt(0) & gap["gap_supply_minus_demand_gwh"].notna(),
        gap["gap_supply_minus_demand_gwh"] / gap["demand_gwh"] * 100.0,
        np.nan,
    )

    percentage = gap["gap_to_demand_percent"]
    conditions = [
        percentage.ge(20),
        percentage.ge(5) & percentage.lt(20),
        percentage.ge(-5) & percentage.lt(5),
        percentage.gt(-20) & percentage.lt(-5),
        percentage.le(-20),
    ]
    choices = [
        "surplus_tinggi",
        "surplus_moderat",
        "relatif_seimbang",
        "defisit_moderat",
        "defisit_tinggi",
    ]
    gap["gap_category"] = np.select(conditions, choices, default="tidak_tersedia")
    gap.loc[~gap["gap_available"], "gap_category"] = "tidak_tersedia"

    gap["data_type"] = "forecast"
    gap["scenario"] = "production_drift_harmonized"
    gap["geography"] = "34_harmonized_modeling_regions"
    gap["gap_stage_version"] = STAGE_VERSION
    gap["catatan_interpretasi"] = (
        "Gap adalah proxy regional berbasis electricity generated minus electricity "
        "distributed. Interpretasi operasional perlu mempertimbangkan interkoneksi "
        "dan aliran listrik lintas wilayah."
    )

    preferred_columns = [
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
        "demand_model_name",
        "demand_model_version",
        "demand_forecast_type",
        "supply_model_name",
        "supply_model_version",
        "supply_forecast_type",
        "raw_model_prediction_gwh",
        "forecast_adjustment",
        "supply_lower_80_gwh",
        "supply_upper_80_gwh",
        "supply_lower_95_gwh",
        "supply_upper_95_gwh",
        "uncertainty_size_bucket",
        "uncertainty_calibration_source",
        "gap_stage_version",
        "catatan_interpretasi",
        "_merge",
    ]
    preferred_columns = [column for column in preferred_columns if column in gap.columns]
    remaining = [column for column in gap.columns if column not in preferred_columns]
    return gap[preferred_columns + remaining].sort_values(
        ["tahun", "provinsi"]
    ).reset_index(drop=True)


def build_national(gap: pd.DataFrame) -> pd.DataFrame:
    national = (
        gap.groupby("tahun", as_index=False)
        .agg(
            total_demand_gwh=("demand_gwh", "sum"),
            total_supply_gwh=("supply_gwh", "sum"),
            total_gap_supply_minus_demand_gwh=(
                "gap_supply_minus_demand_gwh",
                "sum",
            ),
            jumlah_wilayah=("provinsi", "nunique"),
            jumlah_wilayah_gap_lengkap=("gap_available", "sum"),
        )
        .sort_values("tahun")
        .reset_index(drop=True)
    )
    national["supply_to_demand_ratio"] = np.where(
        national["total_demand_gwh"].gt(0),
        national["total_supply_gwh"] / national["total_demand_gwh"],
        np.nan,
    )
    national["gap_to_demand_percent"] = np.where(
        national["total_demand_gwh"].gt(0),
        national["total_gap_supply_minus_demand_gwh"]
        / national["total_demand_gwh"]
        * 100.0,
        np.nan,
    )
    national["demand_growth_yoy_percent"] = (
        national["total_demand_gwh"].pct_change() * 100.0
    )
    national["supply_growth_yoy_percent"] = (
        national["total_supply_gwh"].pct_change() * 100.0
    )
    national["scenario"] = "production_drift_harmonized"
    national["geography"] = "34_harmonized_modeling_regions"
    national["gap_stage_version"] = STAGE_VERSION
    return national


def build_rankings(gap: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    complete = gap.loc[gap["gap_available"]].copy()

    deficit = complete.sort_values(
        ["tahun", "gap_supply_minus_demand_gwh", "provinsi"],
        ascending=[True, True, True],
    ).reset_index(drop=True)
    deficit["rank_deficit"] = (
        deficit.groupby("tahun")["gap_supply_minus_demand_gwh"]
        .rank(ascending=True, method="dense")
        .astype(int)
    )

    surplus = complete.sort_values(
        ["tahun", "gap_supply_minus_demand_gwh", "provinsi"],
        ascending=[True, False, True],
    ).reset_index(drop=True)
    surplus["rank_surplus"] = (
        surplus.groupby("tahun")["gap_supply_minus_demand_gwh"]
        .rank(ascending=False, method="dense")
        .astype(int)
    )
    return deficit, surplus


def build_category_summary(gap: pd.DataFrame) -> pd.DataFrame:
    return (
        gap.groupby(["tahun", "gap_category"], as_index=False)
        .size()
        .rename(columns={"size": "jumlah_wilayah"})
        .sort_values(["tahun", "gap_category"])
        .reset_index(drop=True)
    )


def run_quality_checks(
    demand: pd.DataFrame,
    supply: pd.DataFrame,
    registry: dict[str, object],
    paths: Phase3GPaths,
    gap: pd.DataFrame,
    national: pd.DataFrame,
    ranking_deficit: pd.DataFrame,
    ranking_surplus: pd.DataFrame,
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

    active = registry.get("active_model", {})
    active = active if isinstance(active, dict) else {}

    for label, frame, value_column in [
        ("demand", demand, DEMAND_VALUE_COLUMN),
        ("supply", supply, SUPPLY_VALUE_COLUMN),
    ]:
        add(f"{label}_row_count", len(frame) == EXPECTED_ROW_COUNT, len(frame), EXPECTED_ROW_COUNT)
        add(
            f"{label}_region_count",
            frame["provinsi"].nunique() == EXPECTED_REGION_COUNT,
            int(frame["provinsi"].nunique()),
            EXPECTED_REGION_COUNT,
        )
        add(
            f"{label}_years",
            sorted(frame["tahun"].unique().tolist()) == FORECAST_YEARS,
            sorted(frame["tahun"].unique().tolist()),
            FORECAST_YEARS,
        )
        add(
            f"{label}_no_duplicates",
            not frame.duplicated(["tahun", "provinsi"]).any(),
            int(frame.duplicated(["tahun", "provinsi"]).sum()),
            0,
        )
        add(
            f"{label}_no_missing_values",
            frame[value_column].notna().all(),
            int(frame[value_column].isna().sum()),
            0,
        )
        add(
            f"{label}_nonnegative",
            pd.to_numeric(frame[value_column], errors="coerce").ge(0).all(),
            int(pd.to_numeric(frame[value_column], errors="coerce").lt(0).sum()),
            0,
        )
        add(
            f"{label}_model_is_drift",
            frame["model_name"].astype(str).str.lower().eq("drift").all(),
            sorted(frame["model_name"].astype(str).str.lower().unique().tolist()),
            ["drift"],
        )

    demand_keys = set(map(tuple, demand[["tahun", "provinsi"]].to_numpy()))
    supply_keys = set(map(tuple, supply[["tahun", "provinsi"]].to_numpy()))
    add("demand_supply_key_sets_equal", demand_keys == supply_keys, len(demand_keys ^ supply_keys), 0)
    add(
        "demand_supply_region_sets_equal",
        set(demand["provinsi"]) == set(supply["provinsi"]),
        sorted(set(demand["provinsi"]) ^ set(supply["provinsi"])),
        [],
    )

    add("registry_active_name", active.get("name") == "drift", active.get("name"), "drift")
    add(
        "registry_active_version",
        active.get("version") == "supply_production_drift_v1",
        active.get("version"),
        "supply_production_drift_v1",
    )
    add("registry_active_status", active.get("status") == "production", active.get("status"), "production")
    add(
        "registry_geography",
        active.get("geography") == "34_harmonized_modeling_regions",
        active.get("geography"),
        "34_harmonized_modeling_regions",
    )
    add(
        "registry_supply_hash_matches",
        active.get("canonical_forecast_sha256") == sha256_file(paths.supply_forecast),
        active.get("canonical_forecast_sha256"),
        sha256_file(paths.supply_forecast),
    )

    add("gap_row_count", len(gap) == EXPECTED_ROW_COUNT, len(gap), EXPECTED_ROW_COUNT)
    add(
        "gap_region_count",
        gap["provinsi"].nunique() == EXPECTED_REGION_COUNT,
        int(gap["provinsi"].nunique()),
        EXPECTED_REGION_COUNT,
    )
    add(
        "gap_no_duplicates",
        not gap.duplicated(["tahun", "provinsi"]).any(),
        int(gap.duplicated(["tahun", "provinsi"]).sum()),
        0,
    )
    add("gap_all_keys_matched", gap["_merge"].eq("both").all(), gap["_merge"].value_counts().to_dict(), {"both": EXPECTED_ROW_COUNT})
    add(
        "gap_complete_row_count",
        int(gap["gap_available"].sum()) == EXPECTED_ROW_COUNT,
        int(gap["gap_available"].sum()),
        EXPECTED_ROW_COUNT,
    )
    add(
        "gap_no_missing_demand",
        gap["demand_gwh"].notna().all(),
        int(gap["demand_gwh"].isna().sum()),
        0,
    )
    add(
        "gap_no_missing_supply",
        gap["supply_gwh"].notna().all(),
        int(gap["supply_gwh"].isna().sum()),
        0,
    )
    add(
        "gap_arithmetic_exact",
        np.allclose(
            gap["gap_supply_minus_demand_gwh"].to_numpy(),
            (gap["supply_gwh"] - gap["demand_gwh"]).to_numpy(),
            rtol=0.0,
            atol=1e-9,
        ),
        "all rows",
        "supply - demand",
    )
    add(
        "national_row_count",
        len(national) == len(FORECAST_YEARS),
        len(national),
        len(FORECAST_YEARS),
    )
    add(
        "national_complete_regions",
        national["jumlah_wilayah_gap_lengkap"].eq(EXPECTED_REGION_COUNT).all(),
        national.set_index("tahun")["jumlah_wilayah_gap_lengkap"].to_dict(),
        {year: EXPECTED_REGION_COUNT for year in FORECAST_YEARS},
    )
    expected_national_gap = (
        national["total_supply_gwh"] - national["total_demand_gwh"]
    )
    add(
        "national_gap_arithmetic_exact",
        np.allclose(
            national["total_gap_supply_minus_demand_gwh"].to_numpy(),
            expected_national_gap.to_numpy(),
            rtol=0.0,
            atol=1e-9,
        ),
        "all years",
        "total supply - total demand",
    )
    add(
        "ranking_deficit_row_count",
        len(ranking_deficit) == EXPECTED_ROW_COUNT,
        len(ranking_deficit),
        EXPECTED_ROW_COUNT,
    )
    add(
        "ranking_surplus_row_count",
        len(ranking_surplus) == EXPECTED_ROW_COUNT,
        len(ranking_surplus),
        EXPECTED_ROW_COUNT,
    )
    add(
        "legacy_gap_files_not_overwritten",
        not any(
            path.name in {
                "supply_demand_gap_2011_2030.csv",
                "supply_demand_gap_2011_2030.json",
                "supply_demand_gap_nasional_2011_2030.csv",
            }
            for path in asdict(paths).values()
            if isinstance(path, Path)
        ),
        [],
        [],
    )

    return pd.DataFrame(checks)


def validate_or_raise(checks: pd.DataFrame) -> None:
    failed = checks.loc[~checks["passed"] & checks["severity"].eq("error")]
    if not failed.empty:
        raise ValueError(
            "Phase 3G quality checks gagal:\n"
            + failed.to_string(index=False)
        )


def build_report(
    paths: Phase3GPaths,
    gap: pd.DataFrame,
    national: pd.DataFrame,
    checks: pd.DataFrame,
) -> str:
    latest = national.loc[national["tahun"].eq(FORECAST_END_YEAR)].iloc[0]
    top_deficit = gap.nsmallest(5, "gap_supply_minus_demand_gwh")
    top_surplus = gap.nlargest(5, "gap_supply_minus_demand_gwh")
    critical_failures = int((~checks["passed"] & checks["severity"].eq("error")).sum())

    lines = [
        "# ECADIN Phase 3G — Harmonized Supply-Demand Gap V1",
        "",
        f"Demand input: `{paths.demand_forecast}`",
        f"Supply input: `{paths.supply_forecast}`",
        "",
        "## Contract",
        "",
        "- Geography: **34 harmonized modeling regions**.",
        "- Forecast period: **2025–2030**.",
        f"- Forecast rows: **{len(gap)}**.",
        f"- Complete gap rows: **{int(gap['gap_available'].sum())}**.",
        f"- Critical failures: **{critical_failures}**.",
        "",
        "## National summary",
        "",
        "| Year | Demand GWh | Supply GWh | Gap GWh | Gap % |",
        "|---:|---:|---:|---:|---:|",
    ]
    for _, row in national.iterrows():
        lines.append(
            f"| {int(row['tahun'])} | {row['total_demand_gwh']:,.2f} | "
            f"{row['total_supply_gwh']:,.2f} | "
            f"{row['total_gap_supply_minus_demand_gwh']:,.2f} | "
            f"{row['gap_to_demand_percent']:.2f}% |"
        )

    lines += [
        "",
        f"National gap in {FORECAST_END_YEAR}: "
        f"**{latest['total_gap_supply_minus_demand_gwh']:,.2f} GWh "
        f"({latest['gap_to_demand_percent']:.2f}%)**.",
        "",
        "## Largest deficits",
        "",
        "| Year | Region | Gap GWh |",
        "|---:|---|---:|",
    ]
    for _, row in top_deficit.iterrows():
        lines.append(
            f"| {int(row['tahun'])} | {row['provinsi']} | "
            f"{row['gap_supply_minus_demand_gwh']:,.2f} |"
        )

    lines += [
        "",
        "## Largest surpluses",
        "",
        "| Year | Region | Gap GWh |",
        "|---:|---|---:|",
    ]
    for _, row in top_surplus.iterrows():
        lines.append(
            f"| {int(row['tahun'])} | {row['provinsi']} | "
            f"{row['gap_supply_minus_demand_gwh']:,.2f} |"
        )

    lines += [
        "",
        "## Interpretation",
        "",
        "The gap is a regional planning proxy, not an operational adequacy result. "
        "Generation and distribution can cross administrative boundaries through "
        "interconnected electricity systems.",
        "",
        "This versioned Phase 3G output does not overwrite the existing dashboard "
        "gap files. Dashboard integration must be performed only after the "
        "independent validator passes.",
    ]
    return "\n".join(lines) + "\n"


def export_outputs(
    paths: Phase3GPaths,
    gap: pd.DataFrame,
    national: pd.DataFrame,
    ranking_deficit: pd.DataFrame,
    ranking_surplus: pd.DataFrame,
    category_summary: pd.DataFrame,
    checks: pd.DataFrame,
    metadata: dict[str, object],
    report: str,
) -> None:
    paths.output_dir.mkdir(parents=True, exist_ok=True)
    gap_export = gap.drop(columns=["_merge"], errors="ignore")
    gap_export.to_csv(paths.gap_csv, index=False, encoding="utf-8-sig")
    paths.gap_json.write_text(
        gap_export.to_json(orient="records", force_ascii=False, indent=2),
        encoding="utf-8",
    )
    national.to_csv(paths.national_csv, index=False, encoding="utf-8-sig")
    paths.national_json.write_text(
        national.to_json(orient="records", force_ascii=False, indent=2),
        encoding="utf-8",
    )
    ranking_deficit.drop(columns=["_merge"], errors="ignore").to_csv(
        paths.ranking_deficit_csv, index=False, encoding="utf-8-sig"
    )
    ranking_surplus.drop(columns=["_merge"], errors="ignore").to_csv(
        paths.ranking_surplus_csv, index=False, encoding="utf-8-sig"
    )
    category_summary.to_csv(
        paths.category_summary_csv, index=False, encoding="utf-8-sig"
    )
    checks.to_csv(paths.quality_checks_csv, index=False, encoding="utf-8-sig")
    paths.metadata_json.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    paths.report_markdown.write_text(report, encoding="utf-8")


def run_phase3g(
    *,
    project_root: Optional[str | Path] = None,
    demand_forecast: Optional[str | Path] = None,
    supply_forecast: Optional[str | Path] = None,
    supply_registry: Optional[str | Path] = None,
    output_dir: Optional[str | Path] = None,
    dry_run: bool = False,
) -> dict[str, object]:
    paths = resolve_paths(
        project_root=project_root,
        demand_forecast=demand_forecast,
        supply_forecast=supply_forecast,
        supply_registry=supply_registry,
        output_dir=output_dir,
    )
    demand = load_forecast(paths.demand_forecast, REQUIRED_DEMAND_COLUMNS, "Demand forecast")
    supply = load_forecast(paths.supply_forecast, REQUIRED_SUPPLY_COLUMNS, "Supply forecast")
    registry = load_registry(paths.supply_registry)

    gap = build_gap(demand, supply)
    national = build_national(gap)
    ranking_deficit, ranking_surplus = build_rankings(gap)
    category_summary = build_category_summary(gap)
    checks = run_quality_checks(
        demand,
        supply,
        registry,
        paths,
        gap,
        national,
        ranking_deficit,
        ranking_surplus,
    )
    validate_or_raise(checks)

    generated_at = datetime.now(timezone.utc).isoformat()
    metadata = {
        "stage_version": STAGE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at,
        "forecast_years": FORECAST_YEARS,
        "region_count": int(gap["provinsi"].nunique()),
        "forecast_row_count": int(len(gap)),
        "complete_gap_row_count": int(gap["gap_available"].sum()),
        "demand_input": str(paths.demand_forecast),
        "demand_input_sha256": sha256_file(paths.demand_forecast),
        "supply_input": str(paths.supply_forecast),
        "supply_input_sha256": sha256_file(paths.supply_forecast),
        "supply_registry": str(paths.supply_registry),
        "supply_registry_sha256": sha256_file(paths.supply_registry),
        "demand_models": sorted(demand["model_name"].astype(str).str.lower().unique().tolist()),
        "supply_models": sorted(supply["model_name"].astype(str).str.lower().unique().tolist()),
        "geography": "34_harmonized_modeling_regions",
        "critical_failure_count": int(
            (~checks["passed"] & checks["severity"].eq("error")).sum()
        ),
        "quality_checks_passed": bool(
            checks.loc[checks["severity"].eq("error"), "passed"].all()
        ),
        "legacy_gap_files_modified": False,
        "dashboard_files_modified": False,
        "ready_for_dashboard_integration": bool(
            len(gap) == EXPECTED_ROW_COUNT
            and int(gap["gap_available"].sum()) == EXPECTED_ROW_COUNT
            and checks.loc[checks["severity"].eq("error"), "passed"].all()
        ),
        "output_files": {
            key: str(value)
            for key, value in asdict(paths).items()
            if key.endswith(("_csv", "_json", "_markdown"))
        },
    }
    report = build_report(paths, gap, national, checks)

    print("=" * 88)
    print("ECADIN PHASE 3G - HARMONIZED SUPPLY-DEMAND GAP")
    print("=" * 88)
    print(f"Demand forecast          : {paths.demand_forecast}")
    print(f"Supply forecast          : {paths.supply_forecast}")
    print(f"Supply registry          : {paths.supply_registry}")
    print(f"Output directory         : {paths.output_dir}")
    print(f"Forecast rows            : {len(gap)}")
    print(f"Regions                  : {gap['provinsi'].nunique()}")
    print(f"Years                    : {gap['tahun'].min()}-{gap['tahun'].max()}")
    print(f"Complete gap rows        : {int(gap['gap_available'].sum())}")
    print(f"Critical failures        : {metadata['critical_failure_count']}")
    print(f"Ready for dashboard      : {metadata['ready_for_dashboard_integration']}")

    print("\nNATIONAL GAP")
    print("-" * 88)
    print(
        national[
            [
                "tahun",
                "total_demand_gwh",
                "total_supply_gwh",
                "total_gap_supply_minus_demand_gwh",
                "gap_to_demand_percent",
                "jumlah_wilayah_gap_lengkap",
            ]
        ].to_string(index=False)
    )

    if dry_run:
        print("\n[DRY RUN] Validasi lulus. Tidak ada output yang ditulis.")
    else:
        export_outputs(
            paths,
            gap,
            national,
            ranking_deficit,
            ranking_surplus,
            category_summary,
            checks,
            metadata,
            report,
        )
        print("\nOUTPUTS")
        print("-" * 88)
        for key, value in asdict(paths).items():
            if key.endswith(("_csv", "_json", "_markdown")):
                print(f"{key:28s}: {value}")
        print("\n[DONE] Phase 3G harmonized gap selesai.")

    return {
        "paths": paths,
        "demand": demand,
        "supply": supply,
        "gap": gap,
        "national": national,
        "ranking_deficit": ranking_deficit,
        "ranking_surplus": ranking_surplus,
        "category_summary": category_summary,
        "quality_checks": checks,
        "metadata": metadata,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build the ECADIN Phase 3G harmonized supply-demand gap."
    )
    parser.add_argument("--project-root", type=Path, default=None)
    parser.add_argument("--demand-forecast", type=Path, default=None)
    parser.add_argument("--supply-forecast", type=Path, default=None)
    parser.add_argument("--supply-registry", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    run_phase3g(
        project_root=args.project_root,
        demand_forecast=args.demand_forecast,
        supply_forecast=args.supply_forecast,
        supply_registry=args.supply_registry,
        output_dir=args.output_dir,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
