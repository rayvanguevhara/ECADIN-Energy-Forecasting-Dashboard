"""Audit and reconcile BPS Electricity Statistics PDF publications.

The audit is deliberately non-destructive:
- raw PDFs remain unchanged;
- canonical CSVs remain unchanged;
- differences are reported as review candidates;
- no imputation or automatic revision is performed.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

import fitz

from ecadin_energy.config import PATHS
from ecadin_energy.data_processing.cleaning.annual_province_series import (
    write_csv as _write_csv,
)

AUDIT_ID = "statistik_listrik_bps_pdf_audit"
PARSER_VERSION = "statistik_listrik_bps_audit_v1"

EXPECTED_PDF_FILES = 16
LATEST_PUBLICATION = "statistik-listrik-2020-2024.pdf"
LATEST_START_YEAR = 2020
LATEST_END_YEAR = 2024
EXPECTED_LATEST_TABLES = 57
EXPECTED_REGIONS = 34

REGIONAL_TOLERANCE = Decimal("0.005")
NATIONAL_ROUNDING_TOLERANCE = Decimal("0.05")

BPS_CODE_TO_REGION_ID = {
    "11": "AC",
    "12": "SU",
    "13": "SB",
    "14": "RI",
    "15": "JA",
    "16": "SS",
    "17": "BE",
    "18": "LA",
    "19": "BB",
    "21": "KR",
    "31": "JK",
    "32": "JB",
    "33": "JT",
    "34": "YO",
    "35": "JI",
    "36": "BT",
    "51": "BA",
    "52": "NB",
    "53": "NT",
    "61": "KB",
    "62": "KT",
    "63": "KS",
    "64": "KI",
    "65": "KU",
    "71": "SA",
    "72": "ST",
    "73": "SN",
    "74": "SG",
    "75": "GO",
    "76": "SR",
    "81": "MA",
    "82": "MU",
    "91": "PB",
    "92": "PB",
    "94": "PA",
    "95": "PA",
    "96": "PA",
    "97": "PA",
}

CORE_TABLES = {
    "installed_capacity_mw": {
        "unit": "MW",
        "canonical_path": "data/processed/supply/installed_capacity.csv",
        "title_patterns": (
            r"kapasitas terpasang pembangkit listrik menurut provinsi",
            r"jumlah kapasitas terpasang pembangkit listrik menurut provinsi",
        ),
        "expected_latest_page": 31,
    },
    "local_generation_gwh": {
        "unit": "GWh",
        "canonical_path": "data/processed/supply/local_generation.csv",
        "title_patterns": (
            r"tenaga listrik yang dibangkitkan menurut provinsi",
            r"tenaga listrik y ang dibangkitkan menurut provinsi",
        ),
        "expected_latest_page": 42,
    },
    "distributed_electricity_gwh": {
        "unit": "GWh",
        "canonical_path": "data/processed/demand/distributed_electricity.csv",
        "title_patterns": (
            r"listrik yang didistribusikan menurut provinsi",
            r"listrik yang didistribusikan  menurut provinsi",
            r"banyaknya energi listrik yang didistribusikan menurut provinsi",
        ),
        "expected_latest_page": 60,
    },
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _normalize_space(text: str) -> str:
    return " ".join(text.replace("\xa0", " ").split())


def _parse_coverage(filename: str) -> tuple[int, int]:
    match = re.search(r"(\d{4})-(\d{4})", filename)
    if not match:
        raise ValueError(f"Cannot parse coverage from filename: {filename}")
    return int(match.group(1)), int(match.group(2))


def _parse_decimal(token: str) -> Decimal | None:
    value = token.strip()
    if value in {"...", "…"}:
        return None
    if value in {"–", "-", "−"}:
        return Decimal("0")
    normalized = re.sub(r"\s+", "", value).replace(".", "").replace(",", ".")
    try:
        number = Decimal(normalized)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid Indonesian numeric token: {token!r}") from exc
    if not number.is_finite():
        raise ValueError(f"Non-finite number: {token!r}")
    return number


def _format_decimal(value: Decimal | None) -> str:
    if value is None:
        return ""
    return format(value.quantize(Decimal("0.01")), "f")


def _find_core_page(
    doc: fitz.Document,
    patterns: tuple[str, ...],
) -> int | None:
    for page_index, page in enumerate(doc):
        text = _normalize_space(page.get_text("text"))
        lowered = text.lower()
        if "daftar tabel" in lowered:
            continue
        if not any(re.search(pattern, lowered) for pattern in patterns):
            continue
        if (
            "provinsi/province" in lowered
            or "wilayah operasional" in lowered
            or "operational region" in lowered
        ):
            return page_index + 1
    return None


def _find_legacy_core_page(
    doc: fitz.Document,
    concept: str,
) -> int | None:
    if concept == "installed_capacity_mw":
        patterns = (
            r"kapasitas terpasang.*wilayah operasional",
            r"installed capacit.*operational region",
        )
    elif concept == "local_generation_gwh":
        patterns = (
            r"tenaga listrik yang dibangkitkan.*wilayah operasional",
            r"electricity produced by operational region",
        )
    else:
        patterns = (
            r"listrik yang didistribusikan.*wilayah operasional",
            r"electricity.*distributed.*operational region",
        )

    for page_index, page in enumerate(doc):
        text = _normalize_space(page.get_text("text"))
        lowered = text.lower()
        if "daftar tabel" in lowered:
            continue
        if any(re.search(pattern, lowered) for pattern in patterns):
            return page_index + 1
    return None


def _scan_pdf_inventory(raw_dir: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in sorted(raw_dir.glob("*.pdf")):
        start_year, end_year = _parse_coverage(path.name)
        with fitz.open(path) as doc:
            text_chars = 0
            for page in doc:
                text_chars += len(page.get_text("text"))

            core_pages: dict[str, int | None] = {}
            for variable_name, config in CORE_TABLES.items():
                page_number = _find_core_page(
                    doc,
                    tuple(config["title_patterns"]),
                )
                if page_number is None:
                    page_number = _find_legacy_core_page(doc, variable_name)
                core_pages[variable_name] = page_number

            installed_page_text = ""
            installed_page = core_pages["installed_capacity_mw"]
            if installed_page is not None:
                installed_page_text = _normalize_space(
                    doc[installed_page - 1].get_text("text")
                ).lower()

            if "wilayah operasional" in installed_page_text:
                geography = "operational_region"
                comparison_eligibility = "not_directly_comparable"
            else:
                geography = "province"
                comparison_eligibility = "comparable_after_34_region_harmonization"

            metadata = doc.metadata or {}
            rows.append(
                {
                    "publication_id": (
                        f"statistik_listrik_{start_year}_{end_year}"
                    ),
                    "filename": path.name,
                    "coverage_start_year": start_year,
                    "coverage_end_year": end_year,
                    "page_count": doc.page_count,
                    "size_bytes": path.stat().st_size,
                    "sha256": _sha256(path),
                    "text_characters": text_chars,
                    "text_layer_status": (
                        "usable" if text_chars >= 1000 else "insufficient"
                    ),
                    "geographic_structure": geography,
                    "canonical_comparison_eligibility": comparison_eligibility,
                    "installed_capacity_pdf_page": (
                        core_pages["installed_capacity_mw"] or ""
                    ),
                    "local_generation_pdf_page": (
                        core_pages["local_generation_gwh"] or ""
                    ),
                    "distributed_electricity_pdf_page": (
                        core_pages["distributed_electricity_gwh"] or ""
                    ),
                    "producer": metadata.get("producer", "") or "",
                    "creator": metadata.get("creator", "") or "",
                    "is_latest_publication": (
                        path.name == LATEST_PUBLICATION
                    ),
                    "notes": (
                        "Latest publication used for detailed reconciliation."
                        if path.name == LATEST_PUBLICATION
                        else ""
                    ),
                }
            )
    return rows


def _classify_table(table_number: int) -> tuple[str, str, str]:
    if table_number in {1, 12, 30}:
        return (
            "core_duplicate",
            "reconciliation_only",
            "Already represented by canonical regional variables.",
        )
    if 2 <= table_number <= 11:
        return (
            "supply_capacity_mix",
            "high_priority_context_backlog",
            "Plant-type installed-capacity composition for dashboard context.",
        )
    if 13 <= table_number <= 22:
        return (
            "supply_generation_mix",
            "high_priority_context_backlog",
            "Plant-type generation composition for dashboard context.",
        )
    if 23 <= table_number <= 29:
        return (
            "regional_customer_structure",
            "medium_priority_context_backlog",
            "Provincial customer counts and customer-group composition.",
        )
    if 31 <= table_number <= 36:
        return (
            "regional_demand_composition",
            "high_priority_context_backlog",
            "Provincial distributed electricity by customer group.",
        )
    if 37 <= table_number <= 43:
        return (
            "regional_distribution_value",
            "low_priority_context_backlog",
            "Monetary value of distributed electricity.",
        )
    if 44 <= table_number <= 48:
        return (
            "electricity_workforce",
            "low_priority_context_backlog",
            "Employment and labor compensation context.",
        )
    if 49 <= table_number <= 55:
        return (
            "operations_and_fuel",
            "medium_priority_context_backlog",
            "Operational expenditure and fuel consumption context.",
        )
    return (
        "financial_output",
        "low_priority_context_backlog",
        "Company income, output, intermediate input, and value added.",
    )


def _scan_latest_table_inventory(
    latest_pdf: Path,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with fitz.open(latest_pdf) as doc:
        for page_index, page in enumerate(doc):
            text = _normalize_space(page.get_text("text"))
            match = re.search(
                r"\bTabel\s+(\d+)\s+(.*?)\s+\bTable\b",
                text,
                flags=re.IGNORECASE,
            )
            if not match:
                continue
            table_number = int(match.group(1))
            title = match.group(2).strip()
            if (
                table_number < 1
                or table_number > EXPECTED_LATEST_TABLES
                or len(title) > 300
                or "halaman/page" in title.lower()
            ):
                continue

            category, decision, rationale = _classify_table(table_number)
            rows.append(
                {
                    "publication_filename": latest_pdf.name,
                    "table_number": table_number,
                    "pdf_page": page_index + 1,
                    "printed_page": page_index - 19,
                    "table_title_indonesian": title,
                    "table_category": category,
                    "migration_decision": decision,
                    "rationale": rationale,
                }
            )

    unique: dict[int, dict[str, object]] = {}
    for row in rows:
        table_number = int(row["table_number"])
        if table_number not in unique:
            unique[table_number] = row

    return [unique[number] for number in sorted(unique)]


def _parse_latest_core_page(
    doc: fitz.Document,
    *,
    page_number: int,
) -> tuple[list[dict[str, object]], list[Decimal]]:
    lines = [
        line.strip()
        for line in doc[page_number - 1].get_text("text").splitlines()
        if line.strip()
    ]

    try:
        start_index = lines.index("(6)") + 1
    except ValueError as exc:
        raise ValueError(
            f"Cannot find final column marker on PDF page {page_number}."
        ) from exc

    source_rows: list[dict[str, object]] = []
    index = start_index
    while index < len(lines):
        token = lines[index]
        if token == "INDONESIA":
            total_values = [
                _parse_decimal(value)
                for value in lines[index + 1 : index + 6]
            ]
            if any(value is None for value in total_values):
                raise ValueError(
                    f"National total contains missing value on page {page_number}."
                )
            return source_rows, [
                value for value in total_values if value is not None
            ]

        if re.fullmatch(r"\d{2}", token):
            if index + 6 >= len(lines):
                raise ValueError(
                    f"Incomplete province row on page {page_number}: {token}"
                )
            province_code = token
            province_name = lines[index + 1]
            values = [
                _parse_decimal(value)
                for value in lines[index + 2 : index + 7]
            ]
            source_rows.append(
                {
                    "province_code": province_code,
                    "province_name": province_name,
                    "values": values,
                }
            )
            index += 7
            continue
        index += 1

    raise ValueError(f"INDONESIA total not found on page {page_number}.")


def _load_regions(root: Path) -> dict[str, str]:
    path = root / "data/reference/regions.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {
        row["region_id"]: row["display_name"]
        for row in rows
        if row["is_model_region"].lower() == "true"
    }


def _load_canonical_values(
    root: Path,
    *,
    relative_path: str,
    variable_name: str,
) -> dict[tuple[str, int], Decimal | None]:
    path = root / relative_path
    if not path.is_file():
        raise FileNotFoundError(f"Canonical input is missing: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    values: dict[tuple[str, int], Decimal | None] = {}
    for row in rows:
        text = row[variable_name]
        values[(row["region_id"], int(row["year"]))] = (
            Decimal(text) if text else None
        )
    return values


def _classify_regional_comparison(
    pdf_value: Decimal | None,
    canonical_value: Decimal | None,
) -> str:
    if pdf_value is None and canonical_value is None:
        return "both_missing"
    if pdf_value is None:
        return "pdf_missing_canonical_value"
    if canonical_value is None:
        if pdf_value == 0:
            return "canonical_missing_pdf_zero"
        return "canonical_missing_pdf_value"
    if abs(pdf_value - canonical_value) <= REGIONAL_TOLERANCE:
        return "exact_match"
    return "revision_candidate"


def _comparison_action(status: str) -> str:
    if status == "exact_match":
        return "no_action"
    if status == "canonical_missing_pdf_zero":
        return "review_zero_vs_missing_semantics"
    if status == "revision_candidate":
        return "manual_source_revision_review"
    if status == "both_missing":
        return "retain_missing"
    return "manual_review"


def _build_reconciliation(
    root: Path,
    latest_pdf: Path,
    latest_pages: dict[str, int],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    regions = _load_regions(root)
    reconciliation_rows: list[dict[str, object]] = []
    national_rows: list[dict[str, object]] = []

    with fitz.open(latest_pdf) as doc:
        for variable_name, config in CORE_TABLES.items():
            page_number = latest_pages[variable_name]
            source_rows, reported_totals = _parse_latest_core_page(
                doc,
                page_number=page_number,
            )

            aggregated: dict[tuple[str, int], Decimal] = defaultdict(
                lambda: Decimal("0")
            )
            observed_keys: set[tuple[str, int]] = set()

            for source_row in source_rows:
                code = str(source_row["province_code"])
                if code not in BPS_CODE_TO_REGION_ID:
                    raise ValueError(f"Unknown BPS province code: {code}")
                region_id = BPS_CODE_TO_REGION_ID[code]
                values = source_row["values"]
                for year, value in zip(
                    range(LATEST_START_YEAR, LATEST_END_YEAR + 1),
                    values,
                ):
                    if value is None:
                        continue
                    aggregated[(region_id, year)] += value
                    observed_keys.add((region_id, year))

            canonical = _load_canonical_values(
                root,
                relative_path=str(config["canonical_path"]),
                variable_name=variable_name,
            )

            for region_id in sorted(regions):
                for year in range(LATEST_START_YEAR, LATEST_END_YEAR + 1):
                    pdf_value = (
                        aggregated[(region_id, year)]
                        if (region_id, year) in observed_keys
                        else None
                    )
                    canonical_value = canonical[(region_id, year)]
                    status = _classify_regional_comparison(
                        pdf_value,
                        canonical_value,
                    )
                    difference = (
                        pdf_value - canonical_value
                        if pdf_value is not None
                        and canonical_value is not None
                        else None
                    )
                    reconciliation_rows.append(
                        {
                            "comparison_scope": "regional",
                            "variable_name": variable_name,
                            "unit": config["unit"],
                            "publication_filename": latest_pdf.name,
                            "pdf_page": page_number,
                            "year": year,
                            "region_id": region_id,
                            "region_name": regions[region_id],
                            "pdf_value": _format_decimal(pdf_value),
                            "canonical_value": _format_decimal(
                                canonical_value
                            ),
                            "difference_pdf_minus_canonical": _format_decimal(
                                difference
                            ),
                            "status": status,
                            "action": _comparison_action(status),
                            "note": (
                                "The latest PDF is treated as a revision signal; "
                                "the canonical CSV is not changed automatically."
                                if status != "exact_match"
                                else ""
                            ),
                        }
                    )

            for offset, year in enumerate(
                range(LATEST_START_YEAR, LATEST_END_YEAR + 1)
            ):
                pdf_reported = reported_totals[offset]
                pdf_aggregated = sum(
                    value
                    for (region_id, value_year), value in aggregated.items()
                    if value_year == year
                )
                canonical_values = [
                    value
                    for (region_id, value_year), value in canonical.items()
                    if value_year == year and value is not None
                ]
                canonical_total = sum(canonical_values, Decimal("0"))
                pdf_aggregation_difference = (
                    pdf_aggregated - pdf_reported
                )
                canonical_difference = canonical_total - pdf_reported

                if abs(canonical_difference) <= NATIONAL_ROUNDING_TOLERANCE:
                    canonical_status = "rounding_match"
                else:
                    canonical_status = "revision_candidate"

                national_rows.append(
                    {
                        "comparison_scope": "national_total",
                        "variable_name": variable_name,
                        "unit": config["unit"],
                        "publication_filename": latest_pdf.name,
                        "pdf_page": page_number,
                        "year": year,
                        "region_id": "ID",
                        "region_name": "Indonesia",
                        "pdf_reported_total": _format_decimal(pdf_reported),
                        "pdf_aggregated_34_total": _format_decimal(
                            pdf_aggregated
                        ),
                        "pdf_aggregation_difference": _format_decimal(
                            pdf_aggregation_difference
                        ),
                        "canonical_34_total": _format_decimal(
                            canonical_total
                        ),
                        "canonical_minus_pdf_reported": _format_decimal(
                            canonical_difference
                        ),
                        "canonical_status": canonical_status,
                        "canonical_nonmissing_regions": len(canonical_values),
                        "action": (
                            "manual_source_revision_review"
                            if canonical_status == "revision_candidate"
                            else "no_action"
                        ),
                    }
                )

    return reconciliation_rows, national_rows


def _build_revision_summary(
    reconciliation_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    grouped: dict[tuple[str, int], list[dict[str, object]]] = defaultdict(list)
    for row in reconciliation_rows:
        grouped[(str(row["variable_name"]), int(row["year"]))].append(row)

    rows: list[dict[str, object]] = []
    for (variable_name, year), group_rows in sorted(grouped.items()):
        counts = Counter(str(row["status"]) for row in group_rows)
        revision_differences = [
            abs(Decimal(str(row["difference_pdf_minus_canonical"])))
            for row in group_rows
            if row["status"] == "revision_candidate"
        ]
        signed_revision_sum = sum(
            (
                Decimal(str(row["difference_pdf_minus_canonical"]))
                for row in group_rows
                if row["status"] == "revision_candidate"
            ),
            Decimal("0"),
        )
        rows.append(
            {
                "variable_name": variable_name,
                "year": year,
                "comparisons": len(group_rows),
                "exact_match": counts["exact_match"],
                "revision_candidate": counts["revision_candidate"],
                "canonical_missing_pdf_zero": counts[
                    "canonical_missing_pdf_zero"
                ],
                "other_status": (
                    len(group_rows)
                    - counts["exact_match"]
                    - counts["revision_candidate"]
                    - counts["canonical_missing_pdf_zero"]
                ),
                "max_absolute_revision_difference": _format_decimal(
                    max(revision_differences)
                    if revision_differences
                    else Decimal("0")
                ),
                "signed_revision_difference_sum": _format_decimal(
                    signed_revision_sum
                ),
                "recommended_action": (
                    "manual_revision_review"
                    if counts["revision_candidate"]
                    or counts["canonical_missing_pdf_zero"]
                    else "no_action"
                ),
            }
        )
    return rows


def audit_statistik_listrik_bps(
    *,
    project_root: Path | None = None,
) -> dict[str, object]:
    root = (project_root or PATHS.root).resolve()
    raw_dir = root / "data/raw/bps/statistik_listrik"
    report_dir = root / "outputs/reports/data"

    if not raw_dir.is_dir():
        raise FileNotFoundError(f"Raw PDF directory is missing: {raw_dir}")

    pdf_inventory = _scan_pdf_inventory(raw_dir)
    if len(pdf_inventory) != EXPECTED_PDF_FILES:
        raise ValueError(
            f"Expected {EXPECTED_PDF_FILES} PDF files, "
            f"found {len(pdf_inventory)}."
        )

    latest_pdf = raw_dir / LATEST_PUBLICATION
    if not latest_pdf.is_file():
        raise FileNotFoundError(
            f"Latest publication is missing: {latest_pdf}"
        )

    table_inventory = _scan_latest_table_inventory(latest_pdf)
    latest_row = next(
        row for row in pdf_inventory if row["filename"] == LATEST_PUBLICATION
    )
    latest_pages = {
        "installed_capacity_mw": int(
            latest_row["installed_capacity_pdf_page"]
        ),
        "local_generation_gwh": int(
            latest_row["local_generation_pdf_page"]
        ),
        "distributed_electricity_gwh": int(
            latest_row["distributed_electricity_pdf_page"]
        ),
    }

    reconciliation, national_totals = _build_reconciliation(
        root,
        latest_pdf,
        latest_pages,
    )
    revision_summary = _build_revision_summary(reconciliation)

    report_dir.mkdir(parents=True, exist_ok=True)
    pdf_inventory_path = (
        report_dir / "statistik_listrik_pdf_inventory.csv"
    )
    table_inventory_path = (
        report_dir / "statistik_listrik_table_inventory.csv"
    )
    reconciliation_path = (
        report_dir / "statistik_listrik_reconciliation.csv"
    )
    national_path = (
        report_dir / "statistik_listrik_national_totals.csv"
    )
    revision_summary_path = (
        report_dir / "statistik_listrik_revision_summary.csv"
    )
    summary_path = (
        report_dir / "statistik_listrik_bps_build_summary.json"
    )

    _write_csv(
        pdf_inventory_path,
        pdf_inventory,
        list(pdf_inventory[0]),
    )
    _write_csv(
        table_inventory_path,
        table_inventory,
        list(table_inventory[0]),
    )
    _write_csv(
        reconciliation_path,
        reconciliation,
        list(reconciliation[0]),
    )
    _write_csv(
        national_path,
        national_totals,
        list(national_totals[0]),
    )
    _write_csv(
        revision_summary_path,
        revision_summary,
        list(revision_summary[0]),
    )

    regional_status_counts = Counter(
        str(row["status"]) for row in reconciliation
    )
    national_status_counts = Counter(
        str(row["canonical_status"]) for row in national_totals
    )
    table_decision_counts = Counter(
        str(row["migration_decision"]) for row in table_inventory
    )

    summary = {
        "audit_id": AUDIT_ID,
        "parser_version": PARSER_VERSION,
        "status": "completed",
        "pdf_files": len(pdf_inventory),
        "usable_text_layer_files": sum(
            1
            for row in pdf_inventory
            if row["text_layer_status"] == "usable"
        ),
        "operational_region_publications": sum(
            1
            for row in pdf_inventory
            if row["geographic_structure"] == "operational_region"
        ),
        "province_publications": sum(
            1
            for row in pdf_inventory
            if row["geographic_structure"] == "province"
        ),
        "latest_publication": LATEST_PUBLICATION,
        "latest_table_inventory_rows": len(table_inventory),
        "latest_core_pages": latest_pages,
        "regional_reconciliation_rows": len(reconciliation),
        "regional_status_counts": dict(regional_status_counts),
        "national_total_rows": len(national_totals),
        "national_status_counts": dict(national_status_counts),
        "table_decision_counts": dict(table_decision_counts),
        "canonical_outputs_modified": False,
        "automatic_revision_applied": False,
        "decision": (
            "Use the latest PDF as a reconciliation and revision-review "
            "source. Do not overwrite canonical CSVs automatically."
        ),
        "pdf_inventory_file": str(pdf_inventory_path.relative_to(root)),
        "table_inventory_file": str(table_inventory_path.relative_to(root)),
        "reconciliation_file": str(reconciliation_path.relative_to(root)),
        "national_totals_file": str(national_path.relative_to(root)),
        "revision_summary_file": str(
            revision_summary_path.relative_to(root)
        ),
        "processing_timestamp_utc": (
            datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
        ),
    }
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return summary


def validate_statistik_listrik_bps(
    *,
    project_root: Path | None = None,
) -> dict[str, object]:
    root = (project_root or PATHS.root).resolve()
    report_dir = root / "outputs/reports/data"

    paths = {
        "pdf_inventory": report_dir / "statistik_listrik_pdf_inventory.csv",
        "table_inventory": (
            report_dir / "statistik_listrik_table_inventory.csv"
        ),
        "reconciliation": (
            report_dir / "statistik_listrik_reconciliation.csv"
        ),
        "national_totals": (
            report_dir / "statistik_listrik_national_totals.csv"
        ),
        "revision_summary": (
            report_dir / "statistik_listrik_revision_summary.csv"
        ),
        "summary": (
            report_dir / "statistik_listrik_bps_build_summary.json"
        ),
    }
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing PDF audit outputs: {missing}")

    def read_csv(name: str) -> list[dict[str, str]]:
        with paths[name].open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as handle:
            return list(csv.DictReader(handle))

    pdf_inventory = read_csv("pdf_inventory")
    table_inventory = read_csv("table_inventory")
    reconciliation = read_csv("reconciliation")
    national_totals = read_csv("national_totals")
    revision_summary = read_csv("revision_summary")

    failures: list[str] = []

    if len(pdf_inventory) != 16:
        failures.append(
            f"Expected 16 PDF inventory rows, found {len(pdf_inventory)}."
        )
    if any(row["text_layer_status"] != "usable" for row in pdf_inventory):
        failures.append("Every PDF must have a usable text layer.")
    if sum(
        row["geographic_structure"] == "operational_region"
        for row in pdf_inventory
    ) != 2:
        failures.append("Expected two operational-region publications.")
    if sum(
        row["geographic_structure"] == "province"
        for row in pdf_inventory
    ) != 14:
        failures.append("Expected fourteen province publications.")

    if len(table_inventory) != 57:
        failures.append(
            f"Expected 57 latest table rows, found {len(table_inventory)}."
        )
    table_numbers = {int(row["table_number"]) for row in table_inventory}
    if table_numbers != set(range(1, 58)):
        failures.append("Latest table numbers must be exactly 1-57.")

    expected_core_pages = {
        "1": "31",
        "12": "42",
        "30": "60",
    }
    actual_core_pages = {
        row["table_number"]: row["pdf_page"]
        for row in table_inventory
        if row["table_number"] in expected_core_pages
    }
    if actual_core_pages != expected_core_pages:
        failures.append(
            f"Unexpected latest core pages: {actual_core_pages}."
        )

    if len(reconciliation) != 510:
        failures.append(
            f"Expected 510 regional comparisons, found {len(reconciliation)}."
        )
    status_counts = Counter(row["status"] for row in reconciliation)
    expected_status_counts = {
        "exact_match": 478,
        "revision_candidate": 30,
        "canonical_missing_pdf_zero": 2,
    }
    if dict(status_counts) != expected_status_counts:
        failures.append(
            f"Unexpected regional status counts: {dict(status_counts)}."
        )

    variable_counts = Counter(
        row["variable_name"] for row in reconciliation
    )
    if set(variable_counts.values()) != {170} or len(variable_counts) != 3:
        failures.append(
            f"Each core variable must have 170 comparisons: "
            f"{dict(variable_counts)}."
        )

    distributed_status = Counter(
        row["status"]
        for row in reconciliation
        if row["variable_name"] == "distributed_electricity_gwh"
    )
    if distributed_status != Counter({"exact_match": 170}):
        failures.append(
            "Distributed electricity must reconcile 170/170 exactly."
        )

    if len(national_totals) != 15:
        failures.append(
            f"Expected 15 national-total rows, found {len(national_totals)}."
        )
    national_status_counts = Counter(
        row["canonical_status"] for row in national_totals
    )
    if national_status_counts != Counter(
        {"rounding_match": 13, "revision_candidate": 2}
    ):
        failures.append(
            f"Unexpected national status counts: "
            f"{dict(national_status_counts)}."
        )

    national_revision_keys = {
        (row["variable_name"], int(row["year"]))
        for row in national_totals
        if row["canonical_status"] == "revision_candidate"
    }
    if national_revision_keys != {
        ("installed_capacity_mw", 2021),
        ("local_generation_gwh", 2020),
    }:
        failures.append(
            f"Unexpected national revision keys: {national_revision_keys}."
        )

    if len(revision_summary) != 15:
        failures.append(
            f"Expected 15 revision-summary rows, found "
            f"{len(revision_summary)}."
        )

    summary = json.loads(paths["summary"].read_text(encoding="utf-8"))
    if summary["canonical_outputs_modified"]:
        failures.append("Canonical outputs must not be modified.")
    if summary["automatic_revision_applied"]:
        failures.append("Automatic revisions must not be applied.")

    if failures:
        raise ValueError(" | ".join(failures))

    return {
        "status": "valid",
        "pdf_files": len(pdf_inventory),
        "usable_text_layer_files": len(pdf_inventory),
        "operational_region_publications": 2,
        "province_publications": 14,
        "latest_tables": len(table_inventory),
        "regional_comparisons": len(reconciliation),
        "regional_exact_matches": status_counts["exact_match"],
        "regional_revision_candidates": status_counts[
            "revision_candidate"
        ],
        "regional_missing_zero_reviews": status_counts[
            "canonical_missing_pdf_zero"
        ],
        "national_total_rows": len(national_totals),
        "national_revision_candidates": national_status_counts[
            "revision_candidate"
        ],
        "canonical_outputs_modified": False,
    }
