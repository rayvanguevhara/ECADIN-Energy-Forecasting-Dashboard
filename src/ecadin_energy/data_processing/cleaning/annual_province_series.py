"""Shared utilities for annual province-series cleaners.

This module owns the mechanics that are identical across BPS annual province
tables: numeric parsing, source-year validation, region harmonization, hashing,
and deterministic CSV updates.

Dataset-specific cleaners remain responsible for their own missing-value
contracts, total-reconciliation policy, quality warnings, and output schema.
"""

from __future__ import annotations

import csv
import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from ecadin_energy.data_processing.harmonization.regions import (
    load_regions,
    resolve_region,
)

MISSING_VALUE_MARKERS = {"", "-", "–", "—"}


@dataclass(frozen=True)
class ParsedAnnualProvinceFile:
    """Parsed representation of one annual BPS province CSV."""

    path: Path
    year: int
    file_sha256: str
    source_rows: int
    missing_source_names: tuple[str, ...]
    reported_indonesia_total: Decimal
    values_by_region_id: dict[str, Decimal]
    source_contributors_by_region_id: dict[str, int]

    @property
    def reported_indonesia_total_gwh(self) -> Decimal:
        """Backward-compatible alias for existing electricity cleaners."""
        return self.reported_indonesia_total

    @property
    def missing_source_values(self) -> int:
        return len(self.missing_source_names)

    @property
    def source_missing_values(self) -> int:
        """Compatibility alias used by the local-generation audit."""
        return len(self.missing_source_names)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_decimal(value: str, *, context: str) -> Decimal | None:
    text = value.strip()
    if text in MISSING_VALUE_MARKERS:
        return None

    try:
        parsed = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid numeric value {text!r} at {context}.") from exc

    if not parsed.is_finite() or parsed < 0:
        raise ValueError(f"Invalid non-finite/negative value {text!r} at {context}.")
    return parsed


def extract_filename_year(path: Path) -> int:
    match = re.search(r"(19\d{2}|20\d{2})(?=\.csv$)", path.name)
    if match is None:
        raise ValueError(f"Cannot detect year from filename: {path.name}")
    return int(match.group(1))


def read_annual_province_file(
    path: Path,
    *,
    expected_source_rows: int,
    source_scope: str = "population_pdrb_and_modern_province_sources",
    national_row_name: str = "INDONESIA",
) -> ParsedAnnualProvinceFile:
    """Parse one annual province file and aggregate aliases to model regions."""
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

    filename_year = extract_filename_year(path)
    if content_year != filename_year:
        raise ValueError(
            f"Filename year {filename_year} does not match content year "
            f"{content_year}: {path.name}"
        )

    values_by_region_id: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    contributors_by_region_id: dict[str, int] = defaultdict(int)
    source_names: set[str] = set()
    missing_source_names: list[str] = []
    reported_total: Decimal | None = None
    source_rows = 0

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

        value = parse_decimal(
            row[1],
            context=f"{path.name} row {line_number} ({source_name})",
        )

        if source_name.upper() == national_row_name.upper():
            if value is None:
                raise ValueError(f"Indonesia total is blank in {path.name}.")
            reported_total = value
            continue

        source_rows += 1
        match = resolve_region(source_name, source_scope=source_scope)

        if value is None:
            missing_source_names.append(source_name)
            continue

        values_by_region_id[match.region_id] += value
        contributors_by_region_id[match.region_id] += 1

    if source_rows != expected_source_rows:
        raise ValueError(
            f"Expected {expected_source_rows} province rows in "
            f"{path.name}, found {source_rows}."
        )
    if reported_total is None:
        raise ValueError(f"Indonesia total row is missing in {path.name}.")

    region_ids = set(load_regions())
    unknown = set(values_by_region_id) - region_ids
    if unknown:
        raise ValueError(f"Unknown canonical region IDs in {path.name}: {unknown}")

    return ParsedAnnualProvinceFile(
        path=path,
        year=content_year,
        file_sha256=sha256_file(path),
        source_rows=source_rows,
        missing_source_names=tuple(missing_source_names),
        reported_indonesia_total=reported_total,
        values_by_region_id=dict(values_by_region_id),
        source_contributors_by_region_id=dict(contributors_by_region_id),
    )


def write_csv(
    path: Path,
    rows: list[dict[str, object]],
    fieldnames: list[str],
) -> None:
    """Write a deterministic UTF-8-BOM CSV with explicit column order."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_existing_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def replace_dataset_rows(
    path: Path,
    *,
    dataset_id: str,
    new_rows: list[dict[str, object]],
    fieldnames: list[str],
) -> None:
    """Replace one dataset's rows while preserving all other datasets."""
    existing = [
        row
        for row in read_existing_csv(path)
        if row.get("dataset_id") != dataset_id
    ]
    combined: list[dict[str, object]] = [*existing, *new_rows]
    write_csv(path, combined, fieldnames)


def format_decimal(value: Decimal | None) -> str:
    if value is None:
        return ""
    return format(value.quantize(Decimal("0.01")), "f")
