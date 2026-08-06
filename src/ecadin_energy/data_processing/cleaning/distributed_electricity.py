"""Clean and harmonize BPS distributed-electricity CSV files.

Canonical output:
    data/processed/demand/distributed_electricity.csv

The canonical table contains exactly one row per 34-region modeling area and
calendar year from 2011 through 2024. The missing 2016 source year remains
explicit as a blank value. This module never imputes or forecasts data.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable

from ecadin_energy.config import PATHS
from ecadin_energy.data_processing.harmonization.regions import (
    load_regions,
    resolve_region,
)

DATASET_ID = "demand_distributed_electricity"
VARIABLE_NAME = "distributed_electricity_gwh"
PARSER_VERSION = "distributed_electricity_cleaner_v1.1"

EXPECTED_START_YEAR = 2011
EXPECTED_END_YEAR = 2024
EXPECTED_MISSING_SOURCE_YEARS = {2016}
EXPECTED_SOURCE_VALUE_GAPS = {("KU", 2011), ("KU", 2012)}
EXPECTED_SOURCE_PROVINCE_ROWS = 38
EXPECTED_MODEL_REGIONS = 34

NATIONAL_TOTAL_TOLERANCE_GWH = Decimal("0.02")
LARGE_YOY_WARNING_THRESHOLD_PCT = Decimal("35")


@dataclass(frozen=True)
class ParsedSourceFile:
    path: Path
    year: int
    file_sha256: str
    source_rows: int
    missing_source_values: int
    reported_indonesia_total_gwh: Decimal
    values_by_region_id: dict[str, Decimal]
    source_contributors_by_region_id: dict[str, int]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_decimal(value: str, *, context: str) -> Decimal | None:
    text = value.strip()
    if text in {"", "-", "–", "—"}:
        return None

    try:
        parsed = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid numeric value {text!r} at {context}.") from exc

    if not parsed.is_finite() or parsed < 0:
        raise ValueError(f"Invalid non-finite/negative value {text!r} at {context}.")
    return parsed


def _extract_filename_year(path: Path) -> int:
    match = re.search(r"(19\d{2}|20\d{2})(?=\.csv$)", path.name)
    if match is None:
        raise ValueError(f"Cannot detect year from filename: {path.name}")
    return int(match.group(1))


def _read_source_file(path: Path) -> ParsedSourceFile:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))

    if len(rows) < 4:
        raise ValueError(f"Source file is too short: {path}")

    if len(rows[2]) < 2:
        raise ValueError(f"Source year row is malformed: {path}")

    try:
        content_year = int(rows[2][1].strip())
    except ValueError as exc:
        raise ValueError(f"Invalid source year in {path}: {rows[2]}") from exc

    filename_year = _extract_filename_year(path)
    if content_year != filename_year:
        raise ValueError(
            f"Filename year {filename_year} does not match content year "
            f"{content_year}: {path.name}"
        )

    values_by_region_id: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    contributors_by_region_id: dict[str, int] = defaultdict(int)
    source_names: set[str] = set()
    reported_total: Decimal | None = None
    source_rows = 0
    missing_source_values = 0

    for line_number, row in enumerate(rows[3:], start=4):
        if len(row) < 2:
            raise ValueError(f"Malformed row {line_number} in {path.name}: {row}")

        source_name = row[0].strip()
        if not source_name:
            raise ValueError(f"Blank province at row {line_number} in {path.name}.")
        if source_name in source_names:
            raise ValueError(
                f"Duplicate source province {source_name!r} in {path.name}."
            )
        source_names.add(source_name)

        value = _parse_decimal(
            row[1],
            context=f"{path.name} row {line_number} ({source_name})",
        )

        if source_name.upper() == "INDONESIA":
            if value is None:
                raise ValueError(f"Indonesia total is blank in {path.name}.")
            reported_total = value
            continue

        source_rows += 1
        match = resolve_region(
            source_name,
            source_scope="population_pdrb_and_modern_province_sources",
        )

        if value is None:
            missing_source_values += 1
            continue

        values_by_region_id[match.region_id] += value
        contributors_by_region_id[match.region_id] += 1

    if source_rows != EXPECTED_SOURCE_PROVINCE_ROWS:
        raise ValueError(
            f"Expected {EXPECTED_SOURCE_PROVINCE_ROWS} province rows in "
            f"{path.name}, found {source_rows}."
        )
    if reported_total is None:
        raise ValueError(f"Indonesia total row is missing in {path.name}.")

    region_ids = set(load_regions())
    unknown = set(values_by_region_id) - region_ids
    if unknown:
        raise ValueError(f"Unknown canonical region IDs in {path.name}: {unknown}")

    # A canonical model region may legitimately have a blank source value.
    # Known example: Kalimantan Utara in 2011–2012. The missing value is
    # preserved and validated later against EXPECTED_SOURCE_VALUE_GAPS.

    return ParsedSourceFile(
        path=path,
        year=content_year,
        file_sha256=_sha256_file(path),
        source_rows=source_rows,
        missing_source_values=missing_source_values,
        reported_indonesia_total_gwh=reported_total,
        values_by_region_id=dict(values_by_region_id),
        source_contributors_by_region_id=dict(contributors_by_region_id),
    )


def _write_csv(
    path: Path,
    rows: list[dict[str, object]],
    fieldnames: list[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _read_existing_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _replace_dataset_rows(
    path: Path,
    *,
    dataset_id: str,
    new_rows: list[dict[str, object]],
    fieldnames: list[str],
) -> None:
    existing = [
        row
        for row in _read_existing_csv(path)
        if row.get("dataset_id") != dataset_id
    ]
    combined: list[dict[str, object]] = [*existing, *new_rows]
    _write_csv(path, combined, fieldnames)


def _format_decimal(value: Decimal | None) -> str:
    if value is None:
        return ""
    return format(value.quantize(Decimal("0.01")), "f")


def _build_quality_flags(
    canonical_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    flags: list[dict[str, object]] = []

    for row in canonical_rows:
        if row["distributed_electricity_gwh"] == "":
            year = int(row["year"])
            if year in EXPECTED_MISSING_SOURCE_YEARS:
                issue_type = "missing_source_year"
                note = (
                    "BPS source file for 2016 is unavailable. Imputation is "
                    "not performed by the cleaner."
                )
            else:
                issue_type = "missing_source_value"
                note = (
                    "The annual BPS file exists, but this canonical region is "
                    "reported with a blank/dash value. The value remains missing."
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

    by_region: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in canonical_rows:
        by_region[str(row["region_id"])].append(row)

    for region_id, rows in by_region.items():
        ordered = sorted(rows, key=lambda item: int(item["year"]))
        previous_year: int | None = None
        previous_value: Decimal | None = None

        for row in ordered:
            year = int(row["year"])
            text_value = str(row["distributed_electricity_gwh"])
            value = Decimal(text_value) if text_value else None

            if (
                value is not None
                and previous_value is not None
                and previous_value != 0
                and previous_year is not None
                and year - previous_year == 1
            ):
                yoy_pct = ((value / previous_value) - Decimal("1")) * Decimal("100")
                if abs(yoy_pct) >= LARGE_YOY_WARNING_THRESHOLD_PCT:
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
                                f"least {LARGE_YOY_WARNING_THRESHOLD_PCT}%. "
                                "Review against official publication; no value "
                                "was modified."
                            ),
                        }
                    )

            if value is not None:
                previous_year = year
                previous_value = value

    return flags


def build_distributed_electricity(
    *,
    project_root: Path | None = None,
) -> dict[str, object]:
    root = (project_root or PATHS.root).resolve()
    raw_dir = root / "data/raw/bps/distributed_electricity"
    output_path = root / "data/processed/demand/distributed_electricity.csv"
    lineage_path = root / "data/processed/master/data_lineage.csv"
    quality_path = root / "data/processed/master/data_quality_flags.csv"
    audit_path = (
        root
        / "outputs/reports/data/distributed_electricity_raw_audit.csv"
    )
    summary_path = (
        root
        / "outputs/reports/data/distributed_electricity_build_summary.json"
    )

    if not raw_dir.is_dir():
        raise FileNotFoundError(f"Raw directory does not exist: {raw_dir}")

    source_files = sorted(raw_dir.glob("*.csv"))
    if not source_files:
        raise FileNotFoundError(f"No CSV source files found in: {raw_dir}")

    parsed_files = [_read_source_file(path) for path in source_files]
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
        load_regions().values(),
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
                    "distributed_electricity_gwh": _format_decimal(value),
                }
            )

    actual_missing_keys = {
        (str(row["region_id"]), int(row["year"]))
        for row in canonical_rows
        if row["distributed_electricity_gwh"] == ""
    }
    expected_missing_keys = {
        (str(region["region_id"]), year)
        for region in regions
        for year in EXPECTED_MISSING_SOURCE_YEARS
    } | EXPECTED_SOURCE_VALUE_GAPS
    if actual_missing_keys != expected_missing_keys:
        raise ValueError(
            "Canonical missing-value contract changed. "
            f"Expected {sorted(expected_missing_keys)}, "
            f"found {sorted(actual_missing_keys)}."
        )

    _write_csv(
        output_path,
        canonical_rows,
        ["region_id", "year", "distributed_electricity_gwh"],
    )

    processing_time = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    lineage_rows: list[dict[str, object]] = []
    audit_rows: list[dict[str, object]] = []

    for item in sorted(parsed_files, key=lambda parsed: parsed.year):
        calculated_total = sum(
            item.values_by_region_id.values(),
            Decimal("0"),
        )
        difference = calculated_total - item.reported_indonesia_total_gwh
        if abs(difference) > NATIONAL_TOTAL_TOLERANCE_GWH:
            raise ValueError(
                f"National total difference exceeds tolerance in {item.path.name}: "
                f"{difference} GWh"
            )

        status = (
            "valid_with_rounding_difference"
            if difference != 0
            else "valid"
        )
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
                "source_missing_values": item.missing_source_values,
                "canonical_regions_with_value": canonical_value_count,
                "reported_indonesia_total_gwh": _format_decimal(
                    item.reported_indonesia_total_gwh
                ),
                "calculated_canonical_total_gwh": _format_decimal(
                    calculated_total
                ),
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

    quality_rows = _build_quality_flags(canonical_rows)
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

    _write_csv(
        audit_path,
        audit_rows,
        list(audit_rows[0]),
    )

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
            1 for row in canonical_rows if row["distributed_electricity_gwh"] != ""
        ),
        "canonical_missing_rows": sum(
            1 for row in canonical_rows if row["distributed_electricity_gwh"] == ""
        ),
        "quality_flags": len(quality_rows),
        "missing_year_flags": sum(
            1 for row in quality_rows if row["issue_type"] == "missing_source_year"
        ),
        "missing_source_value_flags": sum(
            1 for row in quality_rows if row["issue_type"] == "missing_source_value"
        ),
        "large_yoy_warning_flags": sum(
            1
            for row in quality_rows
            if row["issue_type"] == "large_consecutive_yoy_change"
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


def validate_distributed_electricity(
    *,
    project_root: Path | None = None,
) -> dict[str, object]:
    root = (project_root or PATHS.root).resolve()
    data_path = root / "data/processed/demand/distributed_electricity.csv"
    lineage_path = root / "data/processed/master/data_lineage.csv"
    quality_path = root / "data/processed/master/data_quality_flags.csv"
    summary_path = (
        root
        / "outputs/reports/data/distributed_electricity_build_summary.json"
    )

    required = [data_path, lineage_path, quality_path, summary_path]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing distributed-electricity outputs: {missing}")

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

    expected_region_ids = set(load_regions())
    actual_region_ids = {row["region_id"] for row in data_rows}
    if actual_region_ids != expected_region_ids:
        failures.append("Canonical region set does not match regions.csv.")

    expected_years = set(range(EXPECTED_START_YEAR, EXPECTED_END_YEAR + 1))
    actual_years = {int(row["year"]) for row in data_rows}
    if actual_years != expected_years:
        failures.append("Canonical year set is not 2011–2024.")

    missing_rows = [
        row for row in data_rows if row["distributed_electricity_gwh"] == ""
    ]
    expected_missing_keys = {
        (region_id, year)
        for region_id in expected_region_ids
        for year in EXPECTED_MISSING_SOURCE_YEARS
    } | EXPECTED_SOURCE_VALUE_GAPS
    actual_missing_keys = {
        (row["region_id"], int(row["year"])) for row in missing_rows
    }
    if actual_missing_keys != expected_missing_keys:
        failures.append(
            "Canonical missing-value keys do not match the validated raw contract."
        )

    nonmissing_values = [
        Decimal(row["distributed_electricity_gwh"])
        for row in data_rows
        if row["distributed_electricity_gwh"] != ""
    ]
    if any(value < 0 for value in nonmissing_values):
        failures.append("Negative distributed-electricity value detected.")

    if len(lineage_rows) != 13:
        failures.append(f"Expected 13 lineage rows, found {len(lineage_rows)}.")

    missing_year_flags = [
        row for row in quality_rows if row["issue_type"] == "missing_source_year"
    ]
    if len(missing_year_flags) != EXPECTED_MODEL_REGIONS:
        failures.append(
            f"Expected {EXPECTED_MODEL_REGIONS} missing-year flags, "
            f"found {len(missing_year_flags)}."
        )

    missing_value_flags = [
        row for row in quality_rows if row["issue_type"] == "missing_source_value"
    ]
    if len(missing_value_flags) != len(EXPECTED_SOURCE_VALUE_GAPS):
        failures.append(
            f"Expected {len(EXPECTED_SOURCE_VALUE_GAPS)} missing-source-value flags, "
            f"found {len(missing_value_flags)}."
        )

    yoy_flags = [
        row
        for row in quality_rows
        if row["issue_type"] == "large_consecutive_yoy_change"
    ]

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
        "large_yoy_warning_flags": len(yoy_flags),
    }
