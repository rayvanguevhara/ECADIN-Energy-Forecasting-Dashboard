"""Shared parser for annual national category-series CSV files.

This module supports BPS tables whose rows are categories rather than
provinces. Common numeric, hashing, year, and deterministic CSV helpers are
reused from annual_province_series.py.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from ecadin_energy.data_processing.cleaning.annual_province_series import (
    extract_filename_year,
    parse_decimal,
    sha256_file,
)


@dataclass(frozen=True)
class ParsedAnnualCategoryFile:
    path: Path
    year: int
    file_sha256: str
    source_rows: int
    missing_source_labels: tuple[str, ...]
    values_by_category_id: dict[str, Decimal]
    source_labels_by_category_id: dict[str, str]
    reported_total: Decimal

    @property
    def missing_source_values(self) -> int:
        return len(self.missing_source_labels)


def read_annual_category_file(
    path: Path,
    *,
    source_label_to_category_id: dict[str, str],
    total_source_label: str,
) -> ParsedAnnualCategoryFile:
    """Parse one annual category table with a separately reported total."""
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))

    if len(rows) < 4:
        raise ValueError(f"Source file is too short: {path}")

    try:
        content_year = int(rows[2][1].strip())
    except (IndexError, ValueError) as exc:
        raise ValueError(f"Invalid source year row in {path.name}: {rows[2]}") from exc

    filename_year = extract_filename_year(path)
    if content_year != filename_year:
        raise ValueError(
            f"Filename year {filename_year} does not match content year "
            f"{content_year}: {path.name}"
        )

    expected_labels = set(source_label_to_category_id)
    seen_labels: set[str] = set()
    values_by_category_id: dict[str, Decimal] = {}
    source_labels_by_category_id: dict[str, str] = {}
    missing_labels: list[str] = []
    reported_total: Decimal | None = None

    for line_number, row in enumerate(rows[3:], start=4):
        if len(row) < 2:
            raise ValueError(f"Malformed row {line_number} in {path.name}: {row}")

        source_label = row[0].strip()
        if not source_label:
            raise ValueError(f"Blank category at row {line_number} in {path.name}.")
        if source_label in seen_labels:
            raise ValueError(
                f"Duplicate source category {source_label!r} in {path.name}."
            )
        seen_labels.add(source_label)

        value = parse_decimal(
            row[1],
            context=f"{path.name} row {line_number} ({source_label})",
        )

        if source_label == total_source_label:
            if value is None:
                raise ValueError(f"Reported total is blank in {path.name}.")
            reported_total = value
            continue

        if source_label not in source_label_to_category_id:
            raise ValueError(
                f"Unexpected source category {source_label!r} in {path.name}."
            )

        category_id = source_label_to_category_id[source_label]
        source_labels_by_category_id[category_id] = source_label

        if value is None:
            missing_labels.append(source_label)
            continue

        values_by_category_id[category_id] = value

    missing_required_labels = expected_labels - seen_labels
    if missing_required_labels:
        raise ValueError(
            f"Missing source categories in {path.name}: "
            f"{sorted(missing_required_labels)}"
        )
    if total_source_label not in seen_labels or reported_total is None:
        raise ValueError(
            f"Total row {total_source_label!r} is missing in {path.name}."
        )

    return ParsedAnnualCategoryFile(
        path=path,
        year=content_year,
        file_sha256=sha256_file(path),
        source_rows=len(expected_labels),
        missing_source_labels=tuple(missing_labels),
        values_by_category_id=values_by_category_id,
        source_labels_by_category_id=source_labels_by_category_id,
        reported_total=reported_total,
    )
