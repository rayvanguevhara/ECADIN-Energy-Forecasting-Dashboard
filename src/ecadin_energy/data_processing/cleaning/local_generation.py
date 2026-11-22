"""Clean and harmonize BPS local-generation CSV files.

Canonical output:
    data/processed/supply/local_generation.csv

The canonical table contains one row per 34-region modeling area and year from
2011 through 2024. Missing raw observations remain blank. The cleaner never
imputes, forecasts, or silently corrects source values.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from ecadin_energy.config import PATHS
from ecadin_energy.data_processing.harmonization.regions import load_regions

DATASET_ID = "supply_local_generation"
VARIABLE_NAME = "local_generation_gwh"
PARSER_VERSION = "local_generation_cleaner_v1"

EXPECTED_START_YEAR = 2011
EXPECTED_END_YEAR = 2024
EXPECTED_MISSING_SOURCE_YEARS = {2016}
EXPECTED_SOURCE_PROVINCE_ROWS = 38
EXPECTED_MODEL_REGIONS = 34

ROUNDING_TOLERANCE_GWH = Decimal("0.10")
LARGE_YOY_WARNING_THRESHOLD_PCT = Decimal("75")
LARGE_YOY_MIN_ABSOLUTE_CHANGE_GWH = Decimal("100")

STRUCTURAL_NEW_PAPUA_PROVINCES = {
    "PAPUA BARAT DAYA",
    "PAPUA SELATAN",
    "PAPUA TENGAH",
    "PAPUA PEGUNUNGAN",
}


from ecadin_energy.data_processing.cleaning.annual_province_series import (
    ParsedAnnualProvinceFile as ParsedSourceFile,
    extract_filename_year as _extract_filename_year,
    format_decimal as _format_decimal,
    parse_decimal as _parse_decimal,
    read_annual_province_file,
    read_existing_csv as _read_existing_csv,
    replace_dataset_rows as _replace_dataset_rows,
    sha256_file as _sha256_file,
    write_csv as _write_csv,
)


def _classify_total_difference(difference: Decimal) -> str:
    if difference == 0:
        return "valid"
    if abs(difference) <= ROUNDING_TOLERANCE_GWH:
        return "valid_with_rounding_difference"
    return "warning_source_total_mismatch"


def _read_source_file(
    path: Path,
    *,
    project_root: Path | None = None,
) -> ParsedSourceFile:
    return read_annual_province_file(
        path,
        expected_source_rows=EXPECTED_SOURCE_PROVINCE_ROWS,
        expected_unit_token="(GWh)",
        project_root=project_root,
    )


def _count_structural_missing_values(item: ParsedSourceFile) -> int:
    if item.year >= 2023:
        return 0
    return sum(
        1
        for source_name in item.missing_source_names
        if source_name.upper() in STRUCTURAL_NEW_PAPUA_PROVINCES
    )


def _build_quality_flags(
    canonical_rows: list[dict[str, object]],
    parsed_files: list[ParsedSourceFile],
) -> list[dict[str, object]]:
    flags: list[dict[str, object]] = []

    for row in canonical_rows:
        if row["local_generation_gwh"] != "":
            continue

        year = int(row["year"])
        issue_type = (
            "missing_source_year"
            if year in EXPECTED_MISSING_SOURCE_YEARS
            else "missing_source_value"
        )
        note = (
            "BPS source file for 2016 is unavailable. No imputation is performed."
            if issue_type == "missing_source_year"
            else (
                "The province row exists in the BPS source but its local-generation "
                "value is blank or '-'. The canonical value remains missing."
            )
        )
        flags.append(
            {
                "dataset_id": DATASET_ID,
                "region_id": row["region_id"],
                "year": year,
                "variable_name": VARIABLE_NAME,
                "quality_status": "expected_missing",
                "issue_type": issue_type,
                "observed_value": "",
                "comparison_value": "",
                "metric_value": "",
                "treatment": "kept_missing_in_canonical_layer",
                "note": note,
            }
        )

    for item in sorted(parsed_files, key=lambda parsed: parsed.year):
        calculated_total = sum(item.values_by_region_id.values(), Decimal("0"))
        difference = calculated_total - item.reported_indonesia_total_gwh
        status = _classify_total_difference(difference)
        if status != "warning_source_total_mismatch":
            continue

        flags.append(
            {
                "dataset_id": DATASET_ID,
                "region_id": "",
                "year": item.year,
                "variable_name": VARIABLE_NAME,
                "quality_status": "warning",
                "issue_type": "national_total_mismatch",
                "observed_value": _format_decimal(
                    item.reported_indonesia_total_gwh
                ),
                "comparison_value": _format_decimal(calculated_total),
                "metric_value": _format_decimal(difference),
                "treatment": "canonical_uses_sum_of_reported_province_values",
                "note": (
                    "The reported Indonesia total differs from the sum of province "
                    "rows beyond the 0.10 GWh rounding tolerance. Province values "
                    "were retained exactly as reported."
                ),
            }
        )

    by_region: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in canonical_rows:
        by_region[str(row["region_id"])].append(row)

    for region_id, rows in by_region.items():
        ordered = sorted(rows, key=lambda item: int(item["year"]))
        previous_year: int | None = None
        previous_value: Decimal | None = None

        for row in ordered:
            year = int(row["year"])
            text_value = str(row["local_generation_gwh"])
            value = Decimal(text_value) if text_value else None

            if (
                value is not None
                and previous_value is not None
                and previous_year is not None
                and year - previous_year == 1
            ):
                if previous_value != 0:
                    yoy_pct = ((value / previous_value) - Decimal("1")) * Decimal("100")
                    absolute_change = abs(value - previous_value)

                    if (
                        abs(yoy_pct) >= LARGE_YOY_WARNING_THRESHOLD_PCT
                        and absolute_change >= LARGE_YOY_MIN_ABSOLUTE_CHANGE_GWH
                    ):
                        flags.append(
                            {
                                "dataset_id": DATASET_ID,
                                "region_id": region_id,
                                "year": year,
                                "variable_name": VARIABLE_NAME,
                                "quality_status": "warning",
                                "issue_type": "large_consecutive_yoy_change",
                                "observed_value": _format_decimal(value),
                                "comparison_value": _format_decimal(previous_value),
                                "metric_value": _format_decimal(yoy_pct),
                                "treatment": "retained_as_reported",
                                "note": (
                                    "Absolute consecutive year-on-year change is at "
                                    f"least {LARGE_YOY_WARNING_THRESHOLD_PCT}% and "
                                    f"{LARGE_YOY_MIN_ABSOLUTE_CHANGE_GWH} GWh. "
                                    "The value was not modified."
                                ),
                            }
                        )
                elif value >= LARGE_YOY_MIN_ABSOLUTE_CHANGE_GWH:
                    flags.append(
                        {
                            "dataset_id": DATASET_ID,
                            "region_id": region_id,
                            "year": year,
                            "variable_name": VARIABLE_NAME,
                            "quality_status": "warning",
                            "issue_type": "large_zero_base_jump",
                            "observed_value": _format_decimal(value),
                            "comparison_value": _format_decimal(previous_value),
                            "metric_value": _format_decimal(value - previous_value),
                            "treatment": "retained_as_reported",
                            "note": (
                                "Consecutive jump from zero baseline is at least "
                                f"{LARGE_YOY_MIN_ABSOLUTE_CHANGE_GWH} GWh "
                                "(percentage YoY is undefined). "
                                "The value was not modified."
                            ),
                        }
                    )

            if value is not None:
                previous_year = year
                previous_value = value

    return flags


def build_local_generation(
    *,
    project_root: Path | None = None,
) -> dict[str, object]:
    root = (project_root or PATHS.root).resolve()
    raw_dir = root / "data/raw/bps/local_generation"
    output_path = root / "data/processed/supply/local_generation.csv"
    lineage_path = root / "data/processed/master/data_lineage.csv"
    quality_path = root / "data/processed/master/data_quality_flags.csv"
    audit_path = root / "outputs/reports/data/local_generation_raw_audit.csv"
    summary_path = (
        root / "outputs/reports/data/local_generation_build_summary.json"
    )

    if not raw_dir.is_dir():
        raise FileNotFoundError(f"Raw directory does not exist: {raw_dir}")

    source_files = sorted(raw_dir.glob("*.csv"))
    if not source_files:
        raise FileNotFoundError(f"No CSV source files found in: {raw_dir}")

    parsed_files = [
        _read_source_file(path, project_root=root) for path in source_files
    ]
    by_year = {item.year: item for item in parsed_files}
    if len(by_year) != len(parsed_files):
        raise ValueError("Duplicate source year detected.")

    expected_years = set(range(EXPECTED_START_YEAR, EXPECTED_END_YEAR + 1))
    observed_years = set(by_year)
    missing_years = expected_years - observed_years
    unexpected_years = observed_years - expected_years

    if missing_years != EXPECTED_MISSING_SOURCE_YEARS:
        raise ValueError(
            f"Expected missing source years {sorted(EXPECTED_MISSING_SOURCE_YEARS)}, "
            f"found {sorted(missing_years)}."
        )
    if unexpected_years:
        raise ValueError(f"Unexpected source years: {sorted(unexpected_years)}")

    regions = sorted(
        load_regions(project_root=root).values(),
        key=lambda row: int(row["modeling_order"]),
    )
    if len(regions) != EXPECTED_MODEL_REGIONS:
        raise ValueError(
            f"Expected {EXPECTED_MODEL_REGIONS} reference regions, "
            f"found {len(regions)}."
        )

    canonical_rows: list[dict[str, object]] = []
    for region in regions:
        region_id = region["region_id"]
        for year in range(EXPECTED_START_YEAR, EXPECTED_END_YEAR + 1):
            parsed = by_year.get(year)
            value = (
                parsed.values_by_region_id.get(region_id)
                if parsed is not None
                else None
            )
            canonical_rows.append(
                {
                    "region_id": region_id,
                    "year": year,
                    "local_generation_gwh": _format_decimal(value),
                }
            )

    _write_csv(
        output_path,
        canonical_rows,
        ["region_id", "year", "local_generation_gwh"],
    )

    lineage_rows: list[dict[str, object]] = []
    audit_rows: list[dict[str, object]] = []

    for item in sorted(parsed_files, key=lambda parsed: parsed.year):
        calculated_total = sum(item.values_by_region_id.values(), Decimal("0"))
        difference = calculated_total - item.reported_indonesia_total_gwh
        status = _classify_total_difference(difference)

        canonical_value_count = len(item.values_by_region_id)
        lineage_rows.append(
            {
                "dataset_id": DATASET_ID,
                "variable_name": VARIABLE_NAME,
                "source_agency": "BPS",
                "source_file": item.path.name,
                "source_file_sha256": item.file_sha256,
                "source_year": item.year,
                "raw_row_count": item.source_rows + 1,
                "parsed_source_rows": item.source_rows,
                "canonical_rows_with_value": canonical_value_count,
                "reported_indonesia_total": _format_decimal(
                    item.reported_indonesia_total_gwh
                ),
                "calculated_canonical_total": _format_decimal(calculated_total),
                "total_difference": _format_decimal(difference),
                "unit": "GWh",
                "parser_version": PARSER_VERSION,
                "status": status,
            }
        )

        audit_rows.append(
            {
                "year": item.year,
                "source_file": item.path.name,
                "source_file_sha256": item.file_sha256,
                "source_province_rows": item.source_rows,
                "source_missing_values": item.source_missing_values,
                "structural_papua_missing_values": _count_structural_missing_values(item),
                "canonical_regions_with_value": canonical_value_count,
                "reported_indonesia_total_gwh": _format_decimal(
                    item.reported_indonesia_total_gwh
                ),
                "calculated_canonical_total_gwh": _format_decimal(calculated_total),
                "difference_gwh": _format_decimal(difference),
                "total_check_status": status,
            }
        )

    lineage_fields = [
        "dataset_id",
        "variable_name",
        "source_agency",
        "source_file",
        "source_file_sha256",
        "source_year",
        "raw_row_count",
        "parsed_source_rows",
        "canonical_rows_with_value",
        "reported_indonesia_total",
        "calculated_canonical_total",
        "total_difference",
        "unit",
        "parser_version",
        "status",
    ]
    _replace_dataset_rows(
        lineage_path,
        dataset_id=DATASET_ID,
        new_rows=lineage_rows,
        fieldnames=lineage_fields,
    )

    quality_rows = _build_quality_flags(canonical_rows, parsed_files)
    quality_fields = [
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
    ]
    _replace_dataset_rows(
        quality_path,
        dataset_id=DATASET_ID,
        new_rows=quality_rows,
        fieldnames=quality_fields,
    )

    _write_csv(audit_path, audit_rows, list(audit_rows[0]))

    processing_time = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    summary = {
        "dataset_id": DATASET_ID,
        "parser_version": PARSER_VERSION,
        "status": "built",
        "source_files": len(source_files),
        "source_years": sorted(observed_years),
        "missing_source_years": sorted(missing_years),
        "model_regions": len(regions),
        "canonical_rows": len(canonical_rows),
        "canonical_rows_with_value": sum(
            1 for row in canonical_rows if row["local_generation_gwh"] != ""
        ),
        "canonical_missing_rows": sum(
            1 for row in canonical_rows if row["local_generation_gwh"] == ""
        ),
        "quality_flags": len(quality_rows),
        "missing_source_year_flags": sum(
            1 for row in quality_rows if row["issue_type"] == "missing_source_year"
        ),
        "missing_source_value_flags": sum(
            1 for row in quality_rows if row["issue_type"] == "missing_source_value"
        ),
        "national_total_mismatch_flags": sum(
            1 for row in quality_rows if row["issue_type"] == "national_total_mismatch"
        ),
        "large_yoy_warning_flags": sum(
            1
            for row in quality_rows
            if row["issue_type"] == "large_consecutive_yoy_change"
        ),
        "large_zero_base_jump_flags": sum(
            1
            for row in quality_rows
            if row["issue_type"] == "large_zero_base_jump"
        ),
        "output_file": str(output_path.relative_to(root)),
        "lineage_file": str(lineage_path.relative_to(root)),
        "quality_file": str(quality_path.relative_to(root)),
        "audit_file": str(audit_path.relative_to(root)),
        "processing_timestamp_utc": processing_time,
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return summary


def validate_local_generation(
    *,
    project_root: Path | None = None,
) -> dict[str, object]:
    root = (project_root or PATHS.root).resolve()
    data_path = root / "data/processed/supply/local_generation.csv"
    lineage_path = root / "data/processed/master/data_lineage.csv"
    quality_path = root / "data/processed/master/data_quality_flags.csv"
    summary_path = root / "outputs/reports/data/local_generation_build_summary.json"

    required = [data_path, lineage_path, quality_path, summary_path]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing local-generation outputs: {missing}")

    with data_path.open("r", encoding="utf-8-sig", newline="") as handle:
        data_rows = list(csv.DictReader(handle))
    with lineage_path.open("r", encoding="utf-8-sig", newline="") as handle:
        lineage_rows = [
            row for row in csv.DictReader(handle)
            if row["dataset_id"] == DATASET_ID
        ]
    with quality_path.open("r", encoding="utf-8-sig", newline="") as handle:
        quality_rows = [
            row for row in csv.DictReader(handle)
            if row["dataset_id"] == DATASET_ID
        ]

    failures: list[str] = []

    expected_rows = EXPECTED_MODEL_REGIONS * (
        EXPECTED_END_YEAR - EXPECTED_START_YEAR + 1
    )
    if len(data_rows) != expected_rows:
        failures.append(f"Expected {expected_rows} canonical rows, found {len(data_rows)}.")

    keys = [(row["region_id"], int(row["year"])) for row in data_rows]
    if len(set(keys)) != len(keys):
        failures.append("Duplicate region_id-year key detected.")

    expected_region_ids = set(load_regions(project_root=root))
    actual_region_ids = {row["region_id"] for row in data_rows}
    if actual_region_ids != expected_region_ids:
        failures.append("Canonical region set does not match regions.csv.")

    expected_years = set(range(EXPECTED_START_YEAR, EXPECTED_END_YEAR + 1))
    actual_years = {int(row["year"]) for row in data_rows}
    if actual_years != expected_years:
        failures.append("Canonical year set is not 2011–2024.")

    missing_rows = [
        row for row in data_rows if row["local_generation_gwh"] == ""
    ]
    if len(missing_rows) != 39:
        failures.append(f"Expected 39 missing rows, found {len(missing_rows)}.")

    missing_year_counts = defaultdict(int)
    for row in missing_rows:
        missing_year_counts[int(row["year"])] += 1
    expected_missing_counts = {
        2011: 1,
        2012: 1,
        2013: 1,
        2014: 1,
        2016: 34,
        2020: 1,
    }
    if dict(sorted(missing_year_counts.items())) != expected_missing_counts:
        failures.append(
            "Missing-value pattern differs from the audited source contract."
        )

    nonmissing_values = [
        Decimal(row["local_generation_gwh"])
        for row in data_rows
        if row["local_generation_gwh"] != ""
    ]
    if any(value < 0 for value in nonmissing_values):
        failures.append("Negative local-generation value detected.")

    if len(lineage_rows) != 13:
        failures.append(f"Expected 13 lineage rows, found {len(lineage_rows)}.")

    raw_dir = root / "data/raw/bps/local_generation"
    if not raw_dir.is_dir():
        failures.append(f"Raw directory does not exist: {raw_dir}")
    else:
        raw_files = sorted(raw_dir.glob("*.csv"))
        expected_source_files = {row["source_file"] for row in lineage_rows}
        actual_raw_files = {path.name for path in raw_files}
        if actual_raw_files != expected_source_files:
            failures.append(
                "Raw CSV files differ from data_lineage.csv source_file list."
            )
        for row in lineage_rows:
            raw_path = raw_dir / row["source_file"]
            if not raw_path.is_file():
                failures.append(f"Missing raw file in lineage: {row['source_file']}")
                continue
            if _sha256_file(raw_path) != row["source_file_sha256"]:
                failures.append(
                    f"Raw source SHA-256 mismatch for {row['source_file']}."
                )

    observed_by_year: dict[int, list[Decimal]] = defaultdict(list)
    for row in data_rows:
        if row["local_generation_gwh"] != "":
            observed_by_year[int(row["year"])].append(
                Decimal(row["local_generation_gwh"])
            )
    expected_observed_years = expected_years - EXPECTED_MISSING_SOURCE_YEARS
    lineage_years = {int(row["source_year"]) for row in lineage_rows}
    if lineage_years != expected_observed_years:
        failures.append(
            f"Unexpected lineage source_year set: {sorted(lineage_years)}."
        )
    for row in lineage_rows:
        year = int(row["source_year"])
        year_values = observed_by_year.get(year, [])
        if len(year_values) != int(row["canonical_rows_with_value"]):
            failures.append(
                f"Lineage value-count mismatch for {year}: "
                f"processed={len(year_values)}, lineage={row['canonical_rows_with_value']}."
            )
        calculated_total = _format_decimal(sum(year_values, Decimal("0")))
        if calculated_total != row["calculated_canonical_total"]:
            failures.append(
                f"Lineage total mismatch for {year}: "
                f"processed={calculated_total}, lineage={row['calculated_canonical_total']}."
            )

    issue_counts = defaultdict(int)
    for row in quality_rows:
        issue_counts[row["issue_type"]] += 1

    expected_issue_counts = {
        "missing_source_year": 34,
        "missing_source_value": 5,
        "national_total_mismatch": 2,
        "large_consecutive_yoy_change": 25,
        "large_zero_base_jump": 1,
    }
    if dict(sorted(issue_counts.items())) != dict(sorted(expected_issue_counts.items())):
        failures.append(
            f"Quality issue counts differ: {dict(issue_counts)}."
        )

    mismatch_years = {
        int(row["year"])
        for row in quality_rows
        if row["issue_type"] == "national_total_mismatch"
    }
    if mismatch_years != {2013, 2014}:
        failures.append(
            f"Expected national total mismatch years 2013 and 2014, found "
            f"{sorted(mismatch_years)}."
        )

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if (
        summary.get("dataset_id") != DATASET_ID
        or summary.get("canonical_rows") != len(data_rows)
        or summary.get("canonical_rows_with_value") != len(nonmissing_values)
        or summary.get("canonical_missing_rows") != len(missing_rows)
        or summary.get("source_files") != len(lineage_rows)
        or summary.get("quality_flags") != len(quality_rows)
        or summary.get("national_total_mismatch_flags") != issue_counts.get("national_total_mismatch", 0)
        or summary.get("large_yoy_warning_flags") != issue_counts.get("large_consecutive_yoy_change", 0)
        or summary.get("large_zero_base_jump_flags", 0) != issue_counts.get("large_zero_base_jump", 0)
    ):
        failures.append("Build summary JSON does not match validated outputs.")

    if failures:
        raise ValueError(" | ".join(failures))

    return {
        "status": "valid",
        "canonical_rows": len(data_rows),
        "regions": len(actual_region_ids),
        "years": f"{min(actual_years)}-{max(actual_years)}",
        "rows_with_value": len(nonmissing_values),
        "missing_rows": len(missing_rows),
        "lineage_rows": len(lineage_rows),
        "quality_flags": len(quality_rows),
        "national_total_mismatch_flags": issue_counts["national_total_mismatch"],
        "large_yoy_warning_flags": issue_counts["large_consecutive_yoy_change"],
        "large_zero_base_jump_flags": issue_counts.get("large_zero_base_jump", 0),
    }
