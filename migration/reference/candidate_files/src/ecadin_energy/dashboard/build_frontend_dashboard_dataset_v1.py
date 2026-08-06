"""Build the ECADIN Phase 3L production dataset consumed by the React frontend.

The builder converts the canonical Phase 3J dashboard CSV/JSON contract into a
single build-time JSON artifact. It preserves missing historical values as
null, exposes only the 34 harmonized modeling regions, and carries the active
Drift model registry without legacy Ridge metrics or unsupported regional
uncertainty intervals.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import pandas as pd


STAGE_VERSION = "phase3l_frontend_dataset_v1"
EXPECTED_REGIONS = 34
EXPECTED_ROWS = 680
EXPECTED_COMPLETE = 671
EXPECTED_FORECAST_ROWS = 204
EXPECTED_HISTORICAL_MISSING = 9
EXPECTED_YEARS = list(range(2011, 2031))

CODE_BY_REGION = {
    "ACEH": "AC",
    "SUMATERA UTARA": "SU",
    "SUMATERA BARAT": "SB",
    "RIAU": "RI",
    "JAMBI": "JA",
    "SUMATERA SELATAN": "SS",
    "BENGKULU": "BE",
    "LAMPUNG": "LA",
    "KEPULAUAN BANGKA BELITUNG": "BB",
    "KEPULAUAN RIAU": "KR",
    "DKI JAKARTA": "JK",
    "JAWA BARAT": "JB",
    "JAWA TENGAH": "JT",
    "DI YOGYAKARTA": "YO",
    "JAWA TIMUR": "JI",
    "BANTEN": "BT",
    "BALI": "BA",
    "NUSA TENGGARA BARAT": "NB",
    "NUSA TENGGARA TIMUR": "NT",
    "KALIMANTAN BARAT": "KB",
    "KALIMANTAN TENGAH": "KT",
    "KALIMANTAN SELATAN": "KS",
    "KALIMANTAN TIMUR": "KI",
    "KALIMANTAN UTARA": "KU",
    "SULAWESI UTARA": "SA",
    "SULAWESI TENGAH": "ST",
    "SULAWESI SELATAN": "SN",
    "SULAWESI TENGGARA": "SG",
    "GORONTALO": "GO",
    "SULAWESI BARAT": "SR",
    "MALUKU": "MA",
    "MALUKU UTARA": "MU",
    "PAPUA": "PA",
    "PAPUA BARAT": "PB",
}

DISPLAY_BY_REGION = {
    "ACEH": "Aceh",
    "SUMATERA UTARA": "Sumatera Utara",
    "SUMATERA BARAT": "Sumatera Barat",
    "RIAU": "Riau",
    "JAMBI": "Jambi",
    "SUMATERA SELATAN": "Sumatera Selatan",
    "BENGKULU": "Bengkulu",
    "LAMPUNG": "Lampung",
    "KEPULAUAN BANGKA BELITUNG": "Kepulauan Bangka Belitung",
    "KEPULAUAN RIAU": "Kepulauan Riau",
    "DKI JAKARTA": "DKI Jakarta",
    "JAWA BARAT": "Jawa Barat",
    "JAWA TENGAH": "Jawa Tengah",
    "DI YOGYAKARTA": "DI Yogyakarta",
    "JAWA TIMUR": "Jawa Timur",
    "BANTEN": "Banten",
    "BALI": "Bali",
    "NUSA TENGGARA BARAT": "Nusa Tenggara Barat",
    "NUSA TENGGARA TIMUR": "Nusa Tenggara Timur",
    "KALIMANTAN BARAT": "Kalimantan Barat",
    "KALIMANTAN TENGAH": "Kalimantan Tengah",
    "KALIMANTAN SELATAN": "Kalimantan Selatan",
    "KALIMANTAN TIMUR": "Kalimantan Timur",
    "KALIMANTAN UTARA": "Kalimantan Utara",
    "SULAWESI UTARA": "Sulawesi Utara",
    "SULAWESI TENGAH": "Sulawesi Tengah",
    "SULAWESI SELATAN": "Sulawesi Selatan",
    "SULAWESI TENGGARA": "Sulawesi Tenggara",
    "GORONTALO": "Gorontalo",
    "SULAWESI BARAT": "Sulawesi Barat",
    "MALUKU": "Maluku",
    "MALUKU UTARA": "Maluku Utara",
    "PAPUA": "Papua",
    "PAPUA BARAT": "Papua Barat",
}

ISLAND_BY_REGION: dict[str, str] = {}
for region in [
    "ACEH",
    "SUMATERA UTARA",
    "SUMATERA BARAT",
    "RIAU",
    "JAMBI",
    "SUMATERA SELATAN",
    "BENGKULU",
    "LAMPUNG",
    "KEPULAUAN BANGKA BELITUNG",
    "KEPULAUAN RIAU",
]:
    ISLAND_BY_REGION[region] = "Sumatera"
for region in [
    "DKI JAKARTA",
    "JAWA BARAT",
    "JAWA TENGAH",
    "DI YOGYAKARTA",
    "JAWA TIMUR",
    "BANTEN",
]:
    ISLAND_BY_REGION[region] = "Jawa"
for region in ["BALI", "NUSA TENGGARA BARAT", "NUSA TENGGARA TIMUR"]:
    ISLAND_BY_REGION[region] = "Bali & Nusa Tenggara"
for region in [
    "KALIMANTAN BARAT",
    "KALIMANTAN TENGAH",
    "KALIMANTAN SELATAN",
    "KALIMANTAN TIMUR",
    "KALIMANTAN UTARA",
]:
    ISLAND_BY_REGION[region] = "Kalimantan"
for region in [
    "SULAWESI UTARA",
    "SULAWESI TENGAH",
    "SULAWESI SELATAN",
    "SULAWESI TENGGARA",
    "GORONTALO",
    "SULAWESI BARAT",
]:
    ISLAND_BY_REGION[region] = "Sulawesi"
for region in ["MALUKU", "MALUKU UTARA"]:
    ISLAND_BY_REGION[region] = "Maluku"
for region in ["PAPUA", "PAPUA BARAT"]:
    ISLAND_BY_REGION[region] = "Papua"

QUALITY_LEVEL = {
    "observed_complete": "observed",
    "includes_interpolation": "interpolated",
    "available_other": "forecast",
    "incomplete": "incomplete",
}


@dataclass(frozen=True)
class Paths:
    project_root: Path
    dashboard_dir: Path
    frontend_dir: Path
    output_json: Path
    audit_dir: Path
    checks_csv: Path
    metadata_json: Path
    report_md: Path


def resolve_paths(
    project_root: Optional[str | Path] = None,
    dashboard_dir: Optional[str | Path] = None,
    frontend_dir: Optional[str | Path] = None,
) -> Paths:
    root = (
        Path(project_root).expanduser().resolve()
        if project_root is not None
        else Path(os.getenv("ECADIN_PROJECT_ROOT", Path(__file__).resolve().parents[3])).resolve()
    )
    dashboard = Path(dashboard_dir) if dashboard_dir else root / "outputs" / "dashboard"
    frontend = Path(frontend_dir) if frontend_dir else root / "frontend-dashboard"
    if not dashboard.is_absolute():
        dashboard = root / dashboard
    if not frontend.is_absolute():
        frontend = root / frontend
    audit = root / "outputs" / "frontend" / "phase3l"
    return Paths(
        project_root=root,
        dashboard_dir=dashboard.resolve(),
        frontend_dir=frontend.resolve(),
        output_json=(frontend / "src" / "data" / "dashboard-production.json").resolve(),
        audit_dir=audit.resolve(),
        checks_csv=(audit / "phase3l_frontend_dataset_checks.csv").resolve(),
        metadata_json=(audit / "phase3l_frontend_dataset_metadata.json").resolve(),
        report_md=(audit / "PHASE3L_FRONTEND_DATASET.md").resolve(),
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clean(value: Any) -> Any:
    if value is None or pd.isna(value):
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float):
        if math.isnan(value):
            return None
        return float(value)
    if isinstance(value, (bool, int, str)):
        return value
    return value


def add_check(
    rows: list[dict[str, Any]],
    name: str,
    passed: bool,
    observed: Any,
    expected: Any,
    severity: str = "error",
) -> None:
    rows.append(
        {
            "check": name,
            "passed": bool(passed),
            "severity": severity,
            "observed": str(observed),
            "expected": str(expected),
        }
    )


def load_and_validate(paths: Paths) -> tuple[dict[str, Any], pd.DataFrame]:
    required = [
        paths.dashboard_dir / "dashboard_province_detail.csv",
        paths.dashboard_dir / "dashboard_national_timeseries.csv",
        paths.dashboard_dir / "dashboard_model_summary.csv",
        paths.dashboard_dir / "dashboard_metadata.csv",
        paths.dashboard_dir / "dashboard_metadata_v2.csv",
        paths.dashboard_dir / "dashboard_source_registry.json",
        paths.dashboard_dir / "dashboard_phase3j_promotion_manifest.csv",
        paths.dashboard_dir / "dashboard_phase3j_promotion_metadata.json",
    ]
    missing = [path for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "Canonical dashboard files are incomplete:\n- " + "\n- ".join(map(str, missing))
        )

    detail = pd.read_csv(required[0], low_memory=False)
    national = pd.read_csv(required[1], low_memory=False)
    model = pd.read_csv(required[2], low_memory=False)
    metadata = pd.read_csv(required[3], low_memory=False)
    metadata_v2 = pd.read_csv(required[4], low_memory=False)
    registry = json.loads(required[5].read_text(encoding="utf-8-sig"))
    manifest = pd.read_csv(required[6], low_memory=False)
    promotion = json.loads(required[7].read_text(encoding="utf-8-sig"))

    detail["gap_available"] = detail["gap_available"].astype(str).str.lower().map(
        {"true": True, "false": False, "1": True, "0": False}
    ).fillna(detail["gap_available"]).astype(bool)

    checks: list[dict[str, Any]] = []
    add_check(checks, "registry_status", registry.get("status") == "production", registry.get("status"), "production")
    add_check(checks, "registry_legacy_ridge", registry.get("legacy_ridge_used") is False, registry.get("legacy_ridge_used"), False)
    add_check(
        checks,
        "registry_regional_uncertainty",
        registry.get("regional_uncertainty_display_allowed") is False,
        registry.get("regional_uncertainty_display_allowed"),
        False,
    )
    add_check(checks, "promotion_ready", promotion.get("production_ready") is True, promotion.get("production_ready"), True)

    canonical_hashes = registry.get("canonical_files", {})
    for filename, expected_hash in canonical_hashes.items():
        path = paths.dashboard_dir / filename
        add_check(
            checks,
            f"registry_hash:{filename}",
            path.is_file() and sha256_file(path) == expected_hash,
            sha256_file(path) if path.is_file() else "missing",
            expected_hash,
        )

    for row in manifest.itertuples(index=False):
        path = paths.dashboard_dir / str(row.file_name)
        add_check(
            checks,
            f"manifest_hash:{row.file_name}",
            path.is_file() and sha256_file(path) == str(row.sha256),
            sha256_file(path) if path.is_file() else "missing",
            row.sha256,
        )

    add_check(checks, "detail_rows", len(detail) == EXPECTED_ROWS, len(detail), EXPECTED_ROWS)
    add_check(checks, "detail_regions", detail["provinsi"].nunique() == EXPECTED_REGIONS, int(detail["provinsi"].nunique()), EXPECTED_REGIONS)
    add_check(checks, "detail_years", sorted(detail["tahun"].unique().tolist()) == EXPECTED_YEARS, sorted(detail["tahun"].unique().tolist()), EXPECTED_YEARS)
    add_check(checks, "detail_no_duplicates", not detail.duplicated(["tahun", "provinsi"]).any(), int(detail.duplicated(["tahun", "provinsi"]).sum()), 0)
    add_check(checks, "complete_gap_count", int(detail["gap_available"].sum()) == EXPECTED_COMPLETE, int(detail["gap_available"].sum()), EXPECTED_COMPLETE)
    add_check(
        checks,
        "forecast_complete_count",
        int((detail["data_type"].eq("forecast") & detail["gap_available"]).sum()) == EXPECTED_FORECAST_ROWS,
        int((detail["data_type"].eq("forecast") & detail["gap_available"]).sum()),
        EXPECTED_FORECAST_ROWS,
    )
    add_check(
        checks,
        "historical_missing_count",
        int((detail["data_type"].eq("historical") & ~detail["gap_available"]).sum()) == EXPECTED_HISTORICAL_MISSING,
        int((detail["data_type"].eq("historical") & ~detail["gap_available"]).sum()),
        EXPECTED_HISTORICAL_MISSING,
    )
    add_check(checks, "coordinates_complete", detail[["latitude", "longitude"]].notna().all().all(), int(detail[["latitude", "longitude"]].isna().any(axis=1).sum()), 0)
    add_check(checks, "region_mapping_complete", set(detail["provinsi"].unique()) == set(CODE_BY_REGION), sorted(set(detail["provinsi"].unique()) ^ set(CODE_BY_REGION)), [])
    add_check(checks, "model_rows", len(model) == 2, len(model), 2)
    add_check(checks, "models_drift", model["active_model"].astype(str).str.lower().eq("drift").all(), sorted(model["active_model"].astype(str).str.lower().unique().tolist()), ["drift"])
    add_check(checks, "legacy_model_not_reused", ~model["legacy_model_reused"].astype(bool).any(), model["legacy_model_reused"].tolist(), [False, False])
    add_check(checks, "national_rows", len(national) == 20, len(national), 20)

    checks_df = pd.DataFrame(checks)
    failures = checks_df.loc[~checks_df["passed"] & checks_df["severity"].eq("error")]
    if not failures.empty:
        raise ValueError("Phase 3L source validation failed:\n" + failures.to_string(index=False))

    provinces: list[dict[str, Any]] = []
    for region in sorted(detail["provinsi"].unique()):
        group = detail.loc[detail["provinsi"].eq(region)].sort_values("tahun")
        latest = group.iloc[-1]
        series: list[dict[str, Any]] = []
        for row in group.itertuples(index=False):
            values = row._asdict()
            series.append(
                {
                    "year": int(values["tahun"]),
                    "demand_gwh": clean(values["demand_gwh"]),
                    "supply_gwh": clean(values["supply_gwh"]),
                    "gap_gwh": clean(values["gap_supply_minus_demand_gwh"]),
                    "gap_pct": clean(values["gap_to_demand_percent"]),
                    "ratio": clean(values["supply_to_demand_ratio"]),
                    "data_type": str(values["data_type"]),
                    "forecast": str(values["data_type"]) == "forecast",
                    "available": bool(values["gap_available"]),
                    "quality": QUALITY_LEVEL.get(str(values["data_quality_badge"]), "incomplete"),
                    "quality_badge": str(values["data_quality_badge"]),
                    "interpolated": bool(values["demand_is_interpolated"]) or bool(values["supply_is_interpolated"]),
                    "attention": bool(values["attention_flag"]),
                    "attention_reason": clean(values["attention_reason"]),
                    "population_jiwa": clean(values["population_projection_jiwa"]),
                    "demand_model": clean(values["demand_model_name"]),
                    "supply_model": clean(values["supply_model_name"]),
                    "demand_value_status": clean(values["demand_value_status"]),
                    "supply_value_status": clean(values["supply_value_status"]),
                }
            )
        provinces.append(
            {
                "code": CODE_BY_REGION[region],
                "source_name": region,
                "name": DISPLAY_BY_REGION[region],
                "island": ISLAND_BY_REGION[region],
                "lat": float(latest["latitude"]),
                "lng": float(latest["longitude"]),
                "population_2030_jiwa": clean(latest["population_projection_jiwa"]),
                "series": series,
            }
        )

    national_rows: list[dict[str, Any]] = []
    for row in national.sort_values("tahun").itertuples(index=False):
        values = row._asdict()
        national_rows.append(
            {
                "year": int(values["tahun"]),
                "demand_gwh": clean(values["total_demand_gwh"]),
                "supply_gwh": clean(values["total_supply_gwh"]),
                "gap_gwh": clean(values["gap_supply_minus_demand_gwh"]),
                "gap_pct": clean(values["gap_to_demand_percent"]),
                "ratio": clean(values["supply_to_demand_ratio"]),
                "forecast": str(values["data_type"]) == "forecast",
                "data_type": str(values["data_type"]),
                "complete_regions": int(values["jumlah_wilayah_gap_lengkap"]),
                "total_regions": int(values["jumlah_wilayah"]),
                "data_completeness": clean(values["data_completeness"]),
                "demand_growth_yoy_percent": clean(values["demand_growth_yoy_percent"]),
                "supply_growth_yoy_percent": clean(values["supply_growth_yoy_percent"]),
            }
        )

    models: list[dict[str, Any]] = []
    for row in model.itertuples(index=False):
        values = row._asdict()
        models.append(
            {
                "side": str(values["side"]),
                "active_model": str(values["active_model"]),
                "model_version": str(values["model_version"]),
                "status": str(values["status"]),
                "forecast_period": str(values["forecast_period"]),
                "geography": str(values["geography"]),
                "selection_basis": str(values["selection_basis"]),
                "legacy_model_reused": bool(values["legacy_model_reused"]),
                "regional_uncertainty_display_allowed": bool(values["regional_uncertainty_display_allowed"]),
                "note": str(values["note"]),
            }
        )

    payload = {
        "schema_version": STAGE_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_dashboard_stage": registry.get("dashboard_stage_version"),
        "source_registry_status": registry.get("status"),
        "production_ready": bool(promotion.get("production_ready")),
        "geography": "34_harmonized_modeling_regions",
        "period": [2011, 2030],
        "forecast_start": 2025,
        "region_count": EXPECTED_REGIONS,
        "row_count": EXPECTED_ROWS,
        "complete_gap_count": EXPECTED_COMPLETE,
        "historical_incomplete_gap_count": EXPECTED_HISTORICAL_MISSING,
        "regional_uncertainty_display_allowed": False,
        "legacy_ridge_used": False,
        "source_hashes": {
            "dashboard_province_detail.csv": sha256_file(paths.dashboard_dir / "dashboard_province_detail.csv"),
            "dashboard_national_timeseries.csv": sha256_file(paths.dashboard_dir / "dashboard_national_timeseries.csv"),
            "dashboard_model_summary.csv": sha256_file(paths.dashboard_dir / "dashboard_model_summary.csv"),
            "dashboard_source_registry.json": sha256_file(paths.dashboard_dir / "dashboard_source_registry.json"),
        },
        "provinces": provinces,
        "national": national_rows,
        "models": models,
        "metadata": metadata.to_dict("records"),
        "metadata_v2": dict(zip(metadata_v2["key"].astype(str), metadata_v2["value"].astype(str))),
    }
    return payload, checks_df


def write_outputs(paths: Paths, payload: dict[str, Any], checks: pd.DataFrame) -> dict[str, Any]:
    paths.output_json.parent.mkdir(parents=True, exist_ok=True)
    paths.audit_dir.mkdir(parents=True, exist_ok=True)
    temporary = paths.output_json.with_name(f".{paths.output_json.name}.phase3l.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    os.replace(temporary, paths.output_json)
    checks.to_csv(paths.checks_csv, index=False, encoding="utf-8-sig")
    output_hash = sha256_file(paths.output_json)
    metadata = {
        "stage_version": STAGE_VERSION,
        "generated_at_utc": payload["generated_at_utc"],
        "output_json": str(paths.output_json),
        "output_sha256": output_hash,
        "region_count": payload["region_count"],
        "row_count": payload["row_count"],
        "complete_gap_count": payload["complete_gap_count"],
        "historical_incomplete_gap_count": payload["historical_incomplete_gap_count"],
        "active_models": {row["side"]: row["active_model"] for row in payload["models"]},
        "legacy_ridge_used": False,
        "regional_uncertainty_display_allowed": False,
        "quality_checks_passed": bool(checks["passed"].all()),
        "critical_failure_count": int((~checks["passed"] & checks["severity"].eq("error")).sum()),
    }
    paths.metadata_json.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    paths.report_md.write_text(
        f"""# ECADIN Phase 3L — React Frontend Production Dataset

- Output: `{paths.output_json}`
- SHA256: `{output_hash}`
- Regions: **34**
- Period: **2011–2030**
- Rows: **680**
- Complete gaps: **671**
- Historical incomplete gaps: **9**
- Forecast rows: **204**
- Demand model: **Drift**
- Supply model: **Drift V1**
- Legacy Ridge used: **No**
- Regional uncertainty displayed: **No**
- Critical failures: **{metadata['critical_failure_count']}**
""",
        encoding="utf-8",
    )
    return metadata


def build_frontend_dataset(
    *,
    project_root: Optional[str | Path] = None,
    dashboard_dir: Optional[str | Path] = None,
    frontend_dir: Optional[str | Path] = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    paths = resolve_paths(project_root, dashboard_dir, frontend_dir)
    payload, checks = load_and_validate(paths)
    print("=" * 92)
    print("ECADIN PHASE 3L - FRONTEND PRODUCTION DATASET")
    print("=" * 92)
    print(f"Dashboard directory     : {paths.dashboard_dir}")
    print(f"Frontend directory      : {paths.frontend_dir}")
    print(f"Regions                 : {payload['region_count']}")
    print(f"Rows                    : {payload['row_count']}")
    print(f"Years                   : {payload['period'][0]}-{payload['period'][1]}")
    print(f"Checks passed           : {int(checks['passed'].sum())}/{len(checks)}")
    if dry_run:
        print("\n[DRY RUN] Source contract is valid. Frontend JSON was not written.")
        return {"paths": paths, "payload": payload, "checks": checks, "dry_run": True}
    metadata = write_outputs(paths, payload, checks)
    print(f"Output JSON             : {paths.output_json}")
    print(f"Output SHA256           : {metadata['output_sha256']}")
    print("Critical failures       : 0")
    print("\n[DONE] Production dashboard data is ready for the React frontend.")
    return {
        "paths": paths,
        "payload": payload,
        "checks": checks,
        "metadata": metadata,
        "dry_run": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Phase 3L React frontend dataset.")
    parser.add_argument("--project-root", type=Path, default=None)
    parser.add_argument("--dashboard-dir", type=Path, default=None)
    parser.add_argument("--frontend-dir", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    build_frontend_dataset(
        project_root=args.project_root,
        dashboard_dir=args.dashboard_dir,
        frontend_dir=args.frontend_dir,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
