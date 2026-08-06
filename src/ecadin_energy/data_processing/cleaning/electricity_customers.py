"""Clean the national BPS electricity-customer group series.

This dataset is national, not province-level. It is kept outside the regional
demand master and exposed through two canonical tables:

- electricity_customers_by_customer_group.csv
- electricity_customers_total.csv
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from ecadin_energy.config import PATHS
from ecadin_energy.data_processing.cleaning.annual_category_series import (
    ParsedAnnualCategoryFile,
    read_annual_category_file,
)
from ecadin_energy.data_processing.cleaning.annual_province_series import (
    replace_dataset_rows as _replace_dataset_rows,
    write_csv as _write_csv,
)

DATASET_ID = "demand_electricity_customers_by_customer_group"
VARIABLE_NAME = "electricity_customers_count"
PARSER_VERSION = "electricity_customers_cleaner_v1"

EXPECTED_START_YEAR = 1995
EXPECTED_END_YEAR = 2024
EXPECTED_MISSING_SOURCE_YEARS = {2016}
EXPECTED_SOURCE_FILES = 29
EXPECTED_CUSTOMER_GROUPS = 5

TOTAL_SOURCE_LABEL = "All Customer"
LARGE_YOY_WARNING_THRESHOLD_PCT = Decimal("20")
LARGE_YOY_MIN_ABSOLUTE_CHANGE_COUNT = Decimal("100000")

SOURCE_LABEL_TO_CUSTOMER_GROUP_ID = {
    "Social": "social",
    "Households": "households",
    "Bussiness": "business",
    "Industry": "industry",
    "Public": "public",
}
CUSTOMER_GROUP_ORDER = [
    "social",
    "households",
    "business",
    "industry",
    "public",
]


def _format_count(value: Decimal | None) -> str:
    if value is None:
        return ""
    if value != value.to_integral_value():
        raise ValueError(f"Customer count must be an integer, found {value}.")
    return str(int(value))


def _classify_total_difference(difference: Decimal) -> str:
    return "valid" if difference == 0 else "warning_source_total_mismatch"


def _read_source_file(path: Path) -> ParsedAnnualCategoryFile:
    parsed = read_annual_category_file(
        path,
        source_label_to_category_id=SOURCE_LABEL_TO_CUSTOMER_GROUP_ID,
        total_source_label=TOTAL_SOURCE_LABEL,
    )

    all_values = [*parsed.values_by_category_id.values(), parsed.reported_total]
    non_integer = [value for value in all_values if value != value.to_integral_value()]
    if non_integer:
        raise ValueError(
            f"Non-integer customer count detected in {path.name}: {non_integer}"
        )
    return parsed


def _build_quality_flags(
    detail_rows: list[dict[str, object]],
    parsed_files: list[ParsedAnnualCategoryFile],
) -> list[dict[str, object]]:
    flags: list[dict[str, object]] = [
        {
            "dataset_id": DATASET_ID,
            "region_id": "",
            "year": 2016,
            "variable_name": VARIABLE_NAME,
            "quality_status": "expected_missing",
            "issue_type": "missing_source_year",
            "observed_value": "",
            "comparison_value": "",
            "metric_value": "",
            "treatment": "kept_missing_in_canonical_layer",
            "note": (
                "The national BPS source file for 2016 is unavailable. "
                "All five customer-group values and the national total remain blank."
            ),
        }
    ]

    for item in sorted(parsed_files, key=lambda parsed: parsed.year):
        calculated_total = sum(item.values_by_category_id.values(), Decimal("0"))
        difference = calculated_total - item.reported_total
        if _classify_total_difference(difference) != "warning_source_total_mismatch":
            continue

        flags.append(
            {
                "dataset_id": DATASET_ID,
                "region_id": "",
                "year": item.year,
                "variable_name": VARIABLE_NAME,
                "quality_status": "warning",
                "issue_type": "national_total_mismatch",
                "observed_value": _format_count(item.reported_total),
                "comparison_value": _format_count(calculated_total),
                "metric_value": _format_count(difference),
                "treatment": "detail_uses_reported_customer_group_values",
                "note": (
                    "Reported All Customer differs from the sum of the five "
                    "customer groups. Counts are expected to reconcile exactly."
                ),
            }
        )

    by_group: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in detail_rows:
        by_group[str(row["customer_group_id"])].append(row)

    for customer_group_id, rows in by_group.items():
        ordered = sorted(rows, key=lambda row: int(row["year"]))
        previous_year: int | None = None
        previous_value: Decimal | None = None

        for row in ordered:
            year = int(row["year"])
            text_value = str(row["electricity_customers_count"])
            value = Decimal(text_value) if text_value else None

            if (
                value is not None
                and previous_value is not None
                and previous_year is not None
                and year - previous_year == 1
                and previous_value != 0
            ):
                yoy_pct = ((value / previous_value) - Decimal("1")) * Decimal("100")
                absolute_change = abs(value - previous_value)

                if (
                    abs(yoy_pct) >= LARGE_YOY_WARNING_THRESHOLD_PCT
                    and absolute_change >= LARGE_YOY_MIN_ABSOLUTE_CHANGE_COUNT
                ):
                    flags.append(
                        {
                            "dataset_id": DATASET_ID,
                            "region_id": "",
                            "year": year,
                            "variable_name": VARIABLE_NAME,
                            "quality_status": "warning",
                            "issue_type": "large_consecutive_yoy_change",
                            "observed_value": _format_count(value),
                            "comparison_value": _format_count(previous_value),
                            "metric_value": format(
                                yoy_pct.quantize(Decimal("0.01")),
                                "f",
                            ),
                            "treatment": "retained_as_reported",
                            "note": (
                                f"customer_group_id={customer_group_id}; absolute "
                                "consecutive year-on-year change is at least "
                                f"{LARGE_YOY_WARNING_THRESHOLD_PCT}% and "
                                f"{LARGE_YOY_MIN_ABSOLUTE_CHANGE_COUNT} customers. "
                                "The source value is not modified."
                            ),
                        }
                    )

            if value is not None:
                previous_year = year
                previous_value = value

    return flags


def build_electricity_customers(
    *,
    project_root: Path | None = None,
) -> dict[str, object]:
    root = (project_root or PATHS.root).resolve()
    raw_dir = root / "data/raw/bps/electricity_customers"
    reference_path = root / "data/reference/customer_groups.csv"
    detail_path = (
        root
        / "data/processed/demand/electricity_customers_by_customer_group.csv"
    )
    total_path = root / "data/processed/demand/electricity_customers_total.csv"
    lineage_path = root / "data/processed/master/data_lineage.csv"
    quality_path = root / "data/processed/master/data_quality_flags.csv"
    audit_path = root / "outputs/reports/data/electricity_customers_raw_audit.csv"
    summary_path = (
        root / "outputs/reports/data/electricity_customers_build_summary.json"
    )

    if not raw_dir.is_dir():
        raise FileNotFoundError(f"Raw directory does not exist: {raw_dir}")
    if not reference_path.is_file():
        raise FileNotFoundError(
            f"Customer-group reference does not exist: {reference_path}"
        )

    with reference_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reference_rows = list(csv.DictReader(handle))

    reference_ids = [row["customer_group_id"] for row in reference_rows]
    if reference_ids != CUSTOMER_GROUP_ORDER:
        raise ValueError(
            "customer_groups.csv order or IDs differ from the canonical contract."
        )

    source_files = sorted(raw_dir.glob("*.csv"))
    if len(source_files) != EXPECTED_SOURCE_FILES:
        raise ValueError(
            f"Expected {EXPECTED_SOURCE_FILES} source files, found "
            f"{len(source_files)}."
        )

    parsed_files = [_read_source_file(path) for path in source_files]
    by_year = {item.year: item for item in parsed_files}
    if len(by_year) != len(parsed_files):
        raise ValueError("Duplicate source year detected.")

    if any(item.missing_source_values for item in parsed_files):
        raise ValueError("Unexpected blank customer-group value in a source file.")

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

    detail_rows: list[dict[str, object]] = []
    for customer_group_id in CUSTOMER_GROUP_ORDER:
        for year in range(EXPECTED_START_YEAR, EXPECTED_END_YEAR + 1):
            parsed = by_year.get(year)
            value = (
                parsed.values_by_category_id.get(customer_group_id)
                if parsed is not None
                else None
            )
            detail_rows.append(
                {
                    "year": year,
                    "customer_group_id": customer_group_id,
                    "electricity_customers_count": _format_count(value),
                }
            )

    total_rows: list[dict[str, object]] = []
    for year in range(EXPECTED_START_YEAR, EXPECTED_END_YEAR + 1):
        parsed = by_year.get(year)
        total_rows.append(
            {
                "year": year,
                "electricity_customers_count": _format_count(
                    parsed.reported_total if parsed is not None else None
                ),
            }
        )

    _write_csv(
        detail_path,
        detail_rows,
        ["year", "customer_group_id", "electricity_customers_count"],
    )
    _write_csv(
        total_path,
        total_rows,
        ["year", "electricity_customers_count"],
    )

    lineage_rows: list[dict[str, object]] = []
    audit_rows: list[dict[str, object]] = []

    for item in sorted(parsed_files, key=lambda parsed: parsed.year):
        calculated_total = sum(item.values_by_category_id.values(), Decimal("0"))
        difference = calculated_total - item.reported_total
        status = _classify_total_difference(difference)

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
                "canonical_rows_with_value": len(item.values_by_category_id),
                "reported_indonesia_total": _format_count(item.reported_total),
                "calculated_canonical_total": _format_count(calculated_total),
                "total_difference": _format_count(difference),
                "unit": "customers",
                "parser_version": PARSER_VERSION,
                "status": status,
            }
        )

        audit_rows.append(
            {
                "year": item.year,
                "source_file": item.path.name,
                "source_file_sha256": item.file_sha256,
                "source_customer_group_rows": item.source_rows,
                "source_missing_values": item.missing_source_values,
                "reported_all_customer_count": _format_count(item.reported_total),
                "calculated_customer_group_total_count": _format_count(
                    calculated_total
                ),
                "difference_count": _format_count(difference),
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

    quality_rows = _build_quality_flags(detail_rows, parsed_files)
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
        "geographic_scope": "National",
        "source_files": len(source_files),
        "source_years": sorted(observed_years),
        "source_coverage": "1995-2015, 2017-2024",
        "missing_source_years": sorted(missing_years),
        "customer_groups": len(CUSTOMER_GROUP_ORDER),
        "detail_rows": len(detail_rows),
        "detail_rows_with_value": sum(
            1
            for row in detail_rows
            if row["electricity_customers_count"] != ""
        ),
        "detail_missing_rows": sum(
            1
            for row in detail_rows
            if row["electricity_customers_count"] == ""
        ),
        "total_rows": len(total_rows),
        "total_rows_with_value": sum(
            1
            for row in total_rows
            if row["electricity_customers_count"] != ""
        ),
        "total_missing_rows": sum(
            1
            for row in total_rows
            if row["electricity_customers_count"] == ""
        ),
        "lineage_rows": len(lineage_rows),
        "quality_flags": len(quality_rows),
        "national_total_mismatch_flags": sum(
            1
            for row in quality_rows
            if row["issue_type"] == "national_total_mismatch"
        ),
        "large_yoy_warning_flags": sum(
            1
            for row in quality_rows
            if row["issue_type"] == "large_consecutive_yoy_change"
        ),
        "regional_master_eligible": False,
        "regional_master_note": (
            "National customer-group series; not joined to region_id-year master."
        ),
        "detail_file": str(detail_path.relative_to(root)),
        "total_file": str(total_path.relative_to(root)),
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


def validate_electricity_customers(
    *,
    project_root: Path | None = None,
) -> dict[str, object]:
    root = (project_root or PATHS.root).resolve()
    detail_path = (
        root
        / "data/processed/demand/electricity_customers_by_customer_group.csv"
    )
    total_path = root / "data/processed/demand/electricity_customers_total.csv"
    lineage_path = root / "data/processed/master/data_lineage.csv"
    quality_path = root / "data/processed/master/data_quality_flags.csv"
    summary_path = (
        root / "outputs/reports/data/electricity_customers_build_summary.json"
    )

    required = [detail_path, total_path, lineage_path, quality_path, summary_path]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            f"Missing electricity-customers outputs: {missing}"
        )

    with detail_path.open("r", encoding="utf-8-sig", newline="") as handle:
        detail_rows = list(csv.DictReader(handle))
    with total_path.open("r", encoding="utf-8-sig", newline="") as handle:
        total_rows = list(csv.DictReader(handle))
    with lineage_path.open("r", encoding="utf-8-sig", newline="") as handle:
        lineage_rows = [
            row
            for row in csv.DictReader(handle)
            if row["dataset_id"] == DATASET_ID
        ]
    with quality_path.open("r", encoding="utf-8-sig", newline="") as handle:
        quality_rows = [
            row
            for row in csv.DictReader(handle)
            if row["dataset_id"] == DATASET_ID
        ]

    failures: list[str] = []

    if len(detail_rows) != 150:
        failures.append(f"Expected 150 detail rows, found {len(detail_rows)}.")
    if len(total_rows) != 30:
        failures.append(f"Expected 30 total rows, found {len(total_rows)}.")

    detail_keys = [
        (int(row["year"]), row["customer_group_id"])
        for row in detail_rows
    ]
    if len(set(detail_keys)) != len(detail_keys):
        failures.append("Duplicate year-customer_group_id key detected.")

    actual_years = {int(row["year"]) for row in total_rows}
    expected_years = set(range(EXPECTED_START_YEAR, EXPECTED_END_YEAR + 1))
    if actual_years != expected_years:
        failures.append("Total table year set is not 1995-2024.")

    actual_groups = {row["customer_group_id"] for row in detail_rows}
    if actual_groups != set(CUSTOMER_GROUP_ORDER):
        failures.append("Customer-group set differs from the reference contract.")

    detail_missing = [
        row
        for row in detail_rows
        if row["electricity_customers_count"] == ""
    ]
    total_missing = [
        row
        for row in total_rows
        if row["electricity_customers_count"] == ""
    ]
    if (
        len(detail_missing) != 5
        or {int(row["year"]) for row in detail_missing} != {2016}
    ):
        failures.append("Detail missing values must be five 2016 rows.")
    if len(total_missing) != 1 or int(total_missing[0]["year"]) != 2016:
        failures.append("Total missing value must be the 2016 row.")

    observed_detail = [
        row for row in detail_rows if row["electricity_customers_count"] != ""
    ]
    observed_total = [
        row for row in total_rows if row["electricity_customers_count"] != ""
    ]

    if any(
        int(row["electricity_customers_count"]) < 0
        for row in observed_detail
    ):
        failures.append("Negative electricity-customer value detected.")

    detail_by_year: dict[int, int] = defaultdict(int)
    for row in observed_detail:
        detail_by_year[int(row["year"])] += int(
            row["electricity_customers_count"]
        )
    total_by_year = {
        int(row["year"]): int(row["electricity_customers_count"])
        for row in observed_total
    }
    if detail_by_year != total_by_year:
        failures.append(
            "Canonical customer-group sums do not match canonical totals."
        )

    if len(lineage_rows) != 29:
        failures.append(f"Expected 29 lineage rows, found {len(lineage_rows)}.")

    if any(row["status"] != "valid" for row in lineage_rows):
        failures.append("Every observed source total must reconcile exactly.")

    issue_counts: dict[str, int] = defaultdict(int)
    for row in quality_rows:
        issue_counts[row["issue_type"]] += 1

    expected_issue_counts = {
        "missing_source_year": 1,
        "large_consecutive_yoy_change": 2,
    }
    if dict(issue_counts) != expected_issue_counts:
        failures.append(f"Quality issue counts differ: {dict(issue_counts)}.")

    warning_pairs = {
        (
            int(row["year"]),
            row["note"].split(";")[0].split("=")[-1],
        )
        for row in quality_rows
        if row["issue_type"] == "large_consecutive_yoy_change"
    }
    if warning_pairs != {
        (2018, "business"),
        (2024, "public"),
    }:
        failures.append(f"Unexpected YoY warning set: {warning_pairs}.")

    if failures:
        raise ValueError(" | ".join(failures))

    return {
        "status": "valid",
        "geographic_scope": "National",
        "detail_rows": len(detail_rows),
        "detail_rows_with_value": len(observed_detail),
        "detail_missing_rows": len(detail_missing),
        "total_rows": len(total_rows),
        "total_rows_with_value": len(observed_total),
        "total_missing_rows": len(total_missing),
        "customer_groups": len(actual_groups),
        "lineage_rows": len(lineage_rows),
        "quality_flags": len(quality_rows),
        "national_total_mismatch_flags": issue_counts[
            "national_total_mismatch"
        ],
        "large_yoy_warning_flags": issue_counts[
            "large_consecutive_yoy_change"
        ],
        "regional_master_eligible": False,
    }
