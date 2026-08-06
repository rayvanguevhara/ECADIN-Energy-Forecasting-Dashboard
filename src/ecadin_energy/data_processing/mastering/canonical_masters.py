"""Build compact canonical master tables for the ECADIN project.

Outputs
-------
data/processed/master/regional_energy_master.csv
    One row per canonical region and year, 2011-2024.

data/processed/master/national_customer_group_master.csv
    One row per national customer group and year, 1995-2024.

This module performs deterministic key-based joins only. It does not impute,
interpolate, forecast, or alter source quality flags.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from ecadin_energy.config import PATHS
from ecadin_energy.data_processing.cleaning.annual_province_series import (
    sha256_file,
    write_csv as _write_csv,
)
from ecadin_energy.data_processing.harmonization.regions import load_regions

REGIONAL_MASTER_ID = "regional_energy_master"
NATIONAL_MASTER_ID = "national_customer_group_master"
PARSER_VERSION = "canonical_masters_builder_v1"

REGIONAL_START_YEAR = 2011
REGIONAL_END_YEAR = 2024
NATIONAL_START_YEAR = 1995
NATIONAL_END_YEAR = 2024
EXPECTED_REGIONS = 34
EXPECTED_CUSTOMER_GROUPS = 5

REGIONAL_COLUMNS = [
    "region_id",
    "year",
    "distributed_electricity_gwh",
    "local_generation_gwh",
    "installed_capacity_mw",
]
NATIONAL_COLUMNS = [
    "year",
    "customer_group_id",
    "electricity_sold_gwh",
    "electricity_customers_count",
]

EXPECTED_REGIONAL_MISSING_COUNTS = {
    "distributed_electricity_gwh": 36,
    "local_generation_gwh": 39,
    "installed_capacity_mw": 38,
}
EXPECTED_NATIONAL_MISSING_COUNTS = {
    "electricity_sold_gwh": 5,
    "electricity_customers_count": 5,
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Required canonical input is missing: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _load_unique_index(
    path: Path,
    *,
    key_fields: tuple[str, ...],
    required_value_fields: tuple[str, ...],
) -> dict[tuple[str, ...], dict[str, str]]:
    rows = _read_csv(path)
    if not rows:
        raise ValueError(f"Canonical input is empty: {path}")

    required = set(key_fields) | set(required_value_fields)
    missing_columns = required - set(rows[0])
    if missing_columns:
        raise ValueError(
            f"Missing columns in {path.name}: {sorted(missing_columns)}"
        )

    index: dict[tuple[str, ...], dict[str, str]] = {}
    for row_number, row in enumerate(rows, start=2):
        key = tuple(str(row[field]).strip() for field in key_fields)
        if any(value == "" for value in key):
            raise ValueError(f"Blank key in {path.name} row {row_number}: {key}")
        if key in index:
            raise ValueError(f"Duplicate key in {path.name}: {key}")
        index[key] = row
    return index


def _validate_numeric_text(
    value: str,
    *,
    integer_only: bool = False,
    context: str,
) -> None:
    if value == "":
        return
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid numeric value in {context}: {value!r}") from exc
    if not number.is_finite():
        raise ValueError(f"Non-finite numeric value in {context}: {value!r}")
    if number < 0:
        raise ValueError(f"Negative numeric value in {context}: {value!r}")
    if integer_only and number != number.to_integral_value():
        raise ValueError(f"Expected integer value in {context}: {value!r}")


def _load_customer_group_order(reference_path: Path) -> list[str]:
    rows = _read_csv(reference_path)
    required = {"customer_group_id", "modeling_order"}
    if not rows or required - set(rows[0]):
        raise ValueError(
            "customer_groups.csv must contain customer_group_id and modeling_order."
        )
    ordered = sorted(rows, key=lambda row: int(row["modeling_order"]))
    ids = [row["customer_group_id"] for row in ordered]
    if len(ids) != EXPECTED_CUSTOMER_GROUPS or len(set(ids)) != len(ids):
        raise ValueError("Customer-group reference must contain 5 unique IDs.")
    return ids


def _build_regional_master(root: Path) -> list[dict[str, object]]:
    distributed_path = (
        root / "data/processed/demand/distributed_electricity.csv"
    )
    generation_path = root / "data/processed/supply/local_generation.csv"
    capacity_path = root / "data/processed/supply/installed_capacity.csv"

    distributed = _load_unique_index(
        distributed_path,
        key_fields=("region_id", "year"),
        required_value_fields=("distributed_electricity_gwh",),
    )
    generation = _load_unique_index(
        generation_path,
        key_fields=("region_id", "year"),
        required_value_fields=("local_generation_gwh",),
    )
    capacity = _load_unique_index(
        capacity_path,
        key_fields=("region_id", "year"),
        required_value_fields=("installed_capacity_mw",),
    )

    regions = sorted(
        load_regions().values(),
        key=lambda row: int(row["modeling_order"]),
    )
    if len(regions) != EXPECTED_REGIONS:
        raise ValueError(
            f"Expected {EXPECTED_REGIONS} canonical regions, found {len(regions)}."
        )

    expected_keys = {
        (region["region_id"], str(year))
        for region in regions
        for year in range(REGIONAL_START_YEAR, REGIONAL_END_YEAR + 1)
    }

    for label, index in [
        ("distributed_electricity", distributed),
        ("local_generation", generation),
        ("installed_capacity", capacity),
    ]:
        actual_keys = set(index)
        if actual_keys != expected_keys:
            missing = sorted(expected_keys - actual_keys)[:10]
            unexpected = sorted(actual_keys - expected_keys)[:10]
            raise ValueError(
                f"{label} key set differs from canonical contract. "
                f"Missing examples={missing}; unexpected examples={unexpected}"
            )

    rows: list[dict[str, object]] = []
    for region in regions:
        region_id = region["region_id"]
        for year in range(REGIONAL_START_YEAR, REGIONAL_END_YEAR + 1):
            key = (region_id, str(year))
            row = {
                "region_id": region_id,
                "year": year,
                "distributed_electricity_gwh": distributed[key][
                    "distributed_electricity_gwh"
                ],
                "local_generation_gwh": generation[key]["local_generation_gwh"],
                "installed_capacity_mw": capacity[key]["installed_capacity_mw"],
            }
            for field in REGIONAL_COLUMNS[2:]:
                _validate_numeric_text(
                    str(row[field]),
                    context=f"{REGIONAL_MASTER_ID} {key} {field}",
                )
            rows.append(row)
    return rows


def _build_national_master(root: Path) -> list[dict[str, object]]:
    sold_path = (
        root
        / "data/processed/demand/electricity_sold_by_customer_group.csv"
    )
    customers_path = (
        root
        / "data/processed/demand/electricity_customers_by_customer_group.csv"
    )
    customer_groups_path = root / "data/reference/customer_groups.csv"

    sold = _load_unique_index(
        sold_path,
        key_fields=("year", "customer_group_id"),
        required_value_fields=("electricity_sold_gwh",),
    )
    customers = _load_unique_index(
        customers_path,
        key_fields=("year", "customer_group_id"),
        required_value_fields=("electricity_customers_count",),
    )
    customer_group_order = _load_customer_group_order(customer_groups_path)

    expected_keys = {
        (str(year), customer_group_id)
        for customer_group_id in customer_group_order
        for year in range(NATIONAL_START_YEAR, NATIONAL_END_YEAR + 1)
    }
    for label, index in [
        ("electricity_sold", sold),
        ("electricity_customers", customers),
    ]:
        actual_keys = set(index)
        if actual_keys != expected_keys:
            missing = sorted(expected_keys - actual_keys)[:10]
            unexpected = sorted(actual_keys - expected_keys)[:10]
            raise ValueError(
                f"{label} key set differs from canonical contract. "
                f"Missing examples={missing}; unexpected examples={unexpected}"
            )

    rows: list[dict[str, object]] = []
    for customer_group_id in customer_group_order:
        for year in range(NATIONAL_START_YEAR, NATIONAL_END_YEAR + 1):
            key = (str(year), customer_group_id)
            row = {
                "year": year,
                "customer_group_id": customer_group_id,
                "electricity_sold_gwh": sold[key]["electricity_sold_gwh"],
                "electricity_customers_count": customers[key][
                    "electricity_customers_count"
                ],
            }
            _validate_numeric_text(
                str(row["electricity_sold_gwh"]),
                context=f"{NATIONAL_MASTER_ID} {key} electricity_sold_gwh",
            )
            _validate_numeric_text(
                str(row["electricity_customers_count"]),
                integer_only=True,
                context=(
                    f"{NATIONAL_MASTER_ID} {key} electricity_customers_count"
                ),
            )
            rows.append(row)
    return rows


def _build_completeness_rows(
    regional_rows: list[dict[str, object]],
    national_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    completeness_rows: list[dict[str, object]] = []

    regional_by_year: dict[int, list[dict[str, object]]] = defaultdict(list)
    for row in regional_rows:
        regional_by_year[int(row["year"])].append(row)

    for year in range(REGIONAL_START_YEAR, REGIONAL_END_YEAR + 1):
        rows = regional_by_year[year]
        missing_counts = {
            field: sum(1 for row in rows if str(row[field]) == "")
            for field in REGIONAL_COLUMNS[2:]
        }
        incomplete_rows = sum(
            1
            for row in rows
            if any(str(row[field]) == "" for field in REGIONAL_COLUMNS[2:])
        )
        if incomplete_rows == 0:
            status = "complete"
        elif year == 2016 and incomplete_rows == EXPECTED_REGIONS:
            status = "expected_missing_source_year"
        else:
            status = "partial_source_values"

        completeness_rows.append(
            {
                "master_id": REGIONAL_MASTER_ID,
                "year": year,
                "expected_rows": EXPECTED_REGIONS,
                "rows_present": len(rows),
                "complete_rows": len(rows) - incomplete_rows,
                "incomplete_rows": incomplete_rows,
                "missing_distributed_electricity_gwh": missing_counts[
                    "distributed_electricity_gwh"
                ],
                "missing_local_generation_gwh": missing_counts[
                    "local_generation_gwh"
                ],
                "missing_installed_capacity_mw": missing_counts[
                    "installed_capacity_mw"
                ],
                "missing_electricity_sold_gwh": "",
                "missing_electricity_customers_count": "",
                "status": status,
            }
        )

    national_by_year: dict[int, list[dict[str, object]]] = defaultdict(list)
    for row in national_rows:
        national_by_year[int(row["year"])].append(row)

    for year in range(NATIONAL_START_YEAR, NATIONAL_END_YEAR + 1):
        rows = national_by_year[year]
        missing_counts = {
            field: sum(1 for row in rows if str(row[field]) == "")
            for field in NATIONAL_COLUMNS[2:]
        }
        incomplete_rows = sum(
            1
            for row in rows
            if any(str(row[field]) == "" for field in NATIONAL_COLUMNS[2:])
        )
        if incomplete_rows == 0:
            status = "complete"
        elif year == 2016 and incomplete_rows == EXPECTED_CUSTOMER_GROUPS:
            status = "expected_missing_source_year"
        else:
            status = "partial_source_values"

        completeness_rows.append(
            {
                "master_id": NATIONAL_MASTER_ID,
                "year": year,
                "expected_rows": EXPECTED_CUSTOMER_GROUPS,
                "rows_present": len(rows),
                "complete_rows": len(rows) - incomplete_rows,
                "incomplete_rows": incomplete_rows,
                "missing_distributed_electricity_gwh": "",
                "missing_local_generation_gwh": "",
                "missing_installed_capacity_mw": "",
                "missing_electricity_sold_gwh": missing_counts[
                    "electricity_sold_gwh"
                ],
                "missing_electricity_customers_count": missing_counts[
                    "electricity_customers_count"
                ],
                "status": status,
            }
        )

    return completeness_rows


def _build_input_hash_rows(root: Path) -> list[dict[str, object]]:
    paths = [
        (
            "regional_input",
            "distributed_electricity",
            root / "data/processed/demand/distributed_electricity.csv",
        ),
        (
            "regional_input",
            "local_generation",
            root / "data/processed/supply/local_generation.csv",
        ),
        (
            "regional_input",
            "installed_capacity",
            root / "data/processed/supply/installed_capacity.csv",
        ),
        (
            "national_input",
            "electricity_sold_by_customer_group",
            root
            / "data/processed/demand/electricity_sold_by_customer_group.csv",
        ),
        (
            "national_input",
            "electricity_customers_by_customer_group",
            root
            / "data/processed/demand/electricity_customers_by_customer_group.csv",
        ),
        (
            "reference",
            "regions",
            root / "data/reference/regions.csv",
        ),
        (
            "reference",
            "customer_groups",
            root / "data/reference/customer_groups.csv",
        ),
    ]

    rows: list[dict[str, object]] = []
    for input_role, input_id, path in paths:
        if not path.is_file():
            raise FileNotFoundError(f"Required master input is missing: {path}")
        rows.append(
            {
                "input_role": input_role,
                "input_id": input_id,
                "relative_path": str(path.relative_to(root)).replace("\\", "/"),
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
        )
    return rows


def build_canonical_masters(
    *,
    project_root: Path | None = None,
) -> dict[str, object]:
    root = (project_root or PATHS.root).resolve()

    regional_path = (
        root / "data/processed/master/regional_energy_master.csv"
    )
    national_path = (
        root / "data/processed/master/national_customer_group_master.csv"
    )
    completeness_path = (
        root / "outputs/reports/data/canonical_master_completeness.csv"
    )
    input_hashes_path = (
        root / "outputs/reports/data/canonical_master_input_hashes.csv"
    )
    summary_path = (
        root / "outputs/reports/data/canonical_master_build_summary.json"
    )

    regional_rows = _build_regional_master(root)
    national_rows = _build_national_master(root)
    completeness_rows = _build_completeness_rows(
        regional_rows,
        national_rows,
    )
    input_hash_rows = _build_input_hash_rows(root)

    _write_csv(regional_path, regional_rows, REGIONAL_COLUMNS)
    _write_csv(national_path, national_rows, NATIONAL_COLUMNS)
    _write_csv(
        completeness_path,
        completeness_rows,
        [
            "master_id",
            "year",
            "expected_rows",
            "rows_present",
            "complete_rows",
            "incomplete_rows",
            "missing_distributed_electricity_gwh",
            "missing_local_generation_gwh",
            "missing_installed_capacity_mw",
            "missing_electricity_sold_gwh",
            "missing_electricity_customers_count",
            "status",
        ],
    )
    _write_csv(
        input_hashes_path,
        input_hash_rows,
        [
            "input_role",
            "input_id",
            "relative_path",
            "sha256",
            "size_bytes",
        ],
    )

    regional_complete_rows = sum(
        1
        for row in regional_rows
        if all(str(row[field]) != "" for field in REGIONAL_COLUMNS[2:])
    )
    national_complete_rows = sum(
        1
        for row in national_rows
        if all(str(row[field]) != "" for field in NATIONAL_COLUMNS[2:])
    )

    summary = {
        "parser_version": PARSER_VERSION,
        "status": "built",
        "regional_master": {
            "output_file": str(regional_path.relative_to(root)),
            "key": ["region_id", "year"],
            "year_coverage": "2011-2024",
            "regions": EXPECTED_REGIONS,
            "rows": len(regional_rows),
            "complete_rows": regional_complete_rows,
            "incomplete_rows": len(regional_rows) - regional_complete_rows,
            "missing_counts": {
                field: sum(
                    1 for row in regional_rows if str(row[field]) == ""
                )
                for field in REGIONAL_COLUMNS[2:]
            },
        },
        "national_customer_group_master": {
            "output_file": str(national_path.relative_to(root)),
            "key": ["year", "customer_group_id"],
            "year_coverage": "1995-2024",
            "customer_groups": EXPECTED_CUSTOMER_GROUPS,
            "rows": len(national_rows),
            "complete_rows": national_complete_rows,
            "incomplete_rows": len(national_rows) - national_complete_rows,
            "missing_counts": {
                field: sum(
                    1 for row in national_rows if str(row[field]) == ""
                )
                for field in NATIONAL_COLUMNS[2:]
            },
        },
        "completeness_file": str(completeness_path.relative_to(root)),
        "input_hashes_file": str(input_hashes_path.relative_to(root)),
        "source_quality_flags_modified": False,
        "imputation_performed": False,
        "processing_timestamp_utc": (
            datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
        ),
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return summary


def validate_canonical_masters(
    *,
    project_root: Path | None = None,
) -> dict[str, object]:
    root = (project_root or PATHS.root).resolve()
    regional_path = (
        root / "data/processed/master/regional_energy_master.csv"
    )
    national_path = (
        root / "data/processed/master/national_customer_group_master.csv"
    )
    completeness_path = (
        root / "outputs/reports/data/canonical_master_completeness.csv"
    )
    input_hashes_path = (
        root / "outputs/reports/data/canonical_master_input_hashes.csv"
    )
    summary_path = (
        root / "outputs/reports/data/canonical_master_build_summary.json"
    )

    required = [
        regional_path,
        national_path,
        completeness_path,
        input_hashes_path,
        summary_path,
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing canonical-master outputs: {missing}")

    regional_rows = _read_csv(regional_path)
    national_rows = _read_csv(national_path)
    completeness_rows = _read_csv(completeness_path)
    input_hash_rows = _read_csv(input_hashes_path)

    failures: list[str] = []

    expected_regional_rows = EXPECTED_REGIONS * (
        REGIONAL_END_YEAR - REGIONAL_START_YEAR + 1
    )
    if len(regional_rows) != expected_regional_rows:
        failures.append(
            f"Expected {expected_regional_rows} regional rows, "
            f"found {len(regional_rows)}."
        )

    regional_keys = [
        (row["region_id"], int(row["year"]))
        for row in regional_rows
    ]
    if len(set(regional_keys)) != len(regional_keys):
        failures.append("Duplicate region_id-year key detected.")

    expected_region_ids = set(load_regions())
    actual_region_ids = {row["region_id"] for row in regional_rows}
    if actual_region_ids != expected_region_ids:
        failures.append("Regional master region set differs from regions.csv.")

    actual_regional_years = {int(row["year"]) for row in regional_rows}
    if actual_regional_years != set(
        range(REGIONAL_START_YEAR, REGIONAL_END_YEAR + 1)
    ):
        failures.append("Regional master year set is not 2011-2024.")

    regional_missing_counts = {
        field: sum(1 for row in regional_rows if row[field] == "")
        for field in REGIONAL_COLUMNS[2:]
    }
    if regional_missing_counts != EXPECTED_REGIONAL_MISSING_COUNTS:
        failures.append(
            f"Unexpected regional missing counts: {regional_missing_counts}."
        )

    regional_complete_rows = sum(
        1
        for row in regional_rows
        if all(row[field] != "" for field in REGIONAL_COLUMNS[2:])
    )
    if regional_complete_rows != 432:
        failures.append(
            f"Expected 432 complete regional rows, found "
            f"{regional_complete_rows}."
        )

    regional_incomplete_keys = {
        (row["region_id"], int(row["year"]))
        for row in regional_rows
        if any(row[field] == "" for field in REGIONAL_COLUMNS[2:])
    }
    expected_regional_incomplete_keys = {
        (region_id, 2016) for region_id in expected_region_ids
    } | {
        ("KU", 2011),
        ("KU", 2012),
        ("YO", 2011),
        ("YO", 2012),
        ("YO", 2013),
        ("YO", 2014),
        ("YO", 2017),
        ("YO", 2018),
        ("YO", 2019),
        ("YO", 2020),
    }
    if regional_incomplete_keys != expected_regional_incomplete_keys:
        failures.append(
            "Regional incomplete-key pattern differs from source contracts."
        )

    expected_national_rows = EXPECTED_CUSTOMER_GROUPS * (
        NATIONAL_END_YEAR - NATIONAL_START_YEAR + 1
    )
    if len(national_rows) != expected_national_rows:
        failures.append(
            f"Expected {expected_national_rows} national rows, "
            f"found {len(national_rows)}."
        )

    national_keys = [
        (int(row["year"]), row["customer_group_id"])
        for row in national_rows
    ]
    if len(set(national_keys)) != len(national_keys):
        failures.append("Duplicate year-customer_group_id key detected.")

    customer_group_ids = set(_load_customer_group_order(
        root / "data/reference/customer_groups.csv"
    ))
    actual_customer_group_ids = {
        row["customer_group_id"] for row in national_rows
    }
    if actual_customer_group_ids != customer_group_ids:
        failures.append(
            "National master customer-group set differs from reference."
        )

    actual_national_years = {int(row["year"]) for row in national_rows}
    if actual_national_years != set(
        range(NATIONAL_START_YEAR, NATIONAL_END_YEAR + 1)
    ):
        failures.append("National master year set is not 1995-2024.")

    national_missing_counts = {
        field: sum(1 for row in national_rows if row[field] == "")
        for field in NATIONAL_COLUMNS[2:]
    }
    if national_missing_counts != EXPECTED_NATIONAL_MISSING_COUNTS:
        failures.append(
            f"Unexpected national missing counts: {national_missing_counts}."
        )

    national_incomplete = [
        row
        for row in national_rows
        if any(row[field] == "" for field in NATIONAL_COLUMNS[2:])
    ]
    if len(national_incomplete) != 5 or {
        int(row["year"]) for row in national_incomplete
    } != {2016}:
        failures.append("National incomplete rows must be five 2016 rows.")

    for row in regional_rows:
        for field in REGIONAL_COLUMNS[2:]:
            _validate_numeric_text(
                row[field],
                context=f"validation regional {row['region_id']} {row['year']} {field}",
            )
    for row in national_rows:
        _validate_numeric_text(
            row["electricity_sold_gwh"],
            context=(
                f"validation national {row['year']} "
                f"{row['customer_group_id']} electricity_sold_gwh"
            ),
        )
        _validate_numeric_text(
            row["electricity_customers_count"],
            integer_only=True,
            context=(
                f"validation national {row['year']} "
                f"{row['customer_group_id']} electricity_customers_count"
            ),
        )

    if len(completeness_rows) != 44:
        failures.append(
            f"Expected 44 completeness rows, found {len(completeness_rows)}."
        )
    if len(input_hash_rows) != 7:
        failures.append(
            f"Expected 7 input-hash rows, found {len(input_hash_rows)}."
        )

    for row in input_hash_rows:
        path = root / row["relative_path"]
        if not path.is_file():
            failures.append(f"Hashed input is missing: {row['relative_path']}")
            continue
        if sha256_file(path) != row["sha256"]:
            failures.append(
                f"Input hash mismatch: {row['relative_path']}"
            )

    if failures:
        raise ValueError(" | ".join(failures))

    return {
        "status": "valid",
        "regional_rows": len(regional_rows),
        "regional_complete_rows": regional_complete_rows,
        "regional_incomplete_rows": len(regional_rows) - regional_complete_rows,
        "regional_regions": len(actual_region_ids),
        "regional_years": "2011-2024",
        "national_rows": len(national_rows),
        "national_complete_rows": len(national_rows) - len(national_incomplete),
        "national_incomplete_rows": len(national_incomplete),
        "national_customer_groups": len(actual_customer_group_ids),
        "national_years": "1995-2024",
        "completeness_rows": len(completeness_rows),
        "input_hash_rows": len(input_hash_rows),
        "imputation_performed": False,
    }
