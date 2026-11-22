"""Canonical ECADIN region reference and harmonization helpers.

This module is intentionally independent from modeling and dashboard code.
All data cleaners and master builders must resolve source province names through
the reference tables instead of embedding local rename dictionaries.
"""

from __future__ import annotations

import csv
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from ecadin_energy.config import PATHS


@dataclass(frozen=True)
class RegionMatch:
    source_name: str
    normalized_alias: str
    region_id: str
    canonical_region_name: str
    mapping_type: str
    aggregation_rule: str
    effective_start_year: int | None = None
    effective_end_year: int | None = None


def normalize_region_key(value: object) -> str:
    """Normalize punctuation, whitespace, and case for deterministic lookup."""
    text = unicodedata.normalize("NFKC", str(value))
    text = text.strip().upper()
    text = re.sub(r"[.\-_/]+", " ", text)
    return re.sub(r"\s+", " ", text)


def _resolve_root(project_root: str | Path | None = None) -> Path:
    return Path(project_root).resolve() if project_root is not None else PATHS.root.resolve()


def _reference_path(filename: str, project_root: str | Path | None = None) -> Path:
    return _resolve_root(project_root) / "data" / "reference" / filename


def _parse_optional_year(value: str | None) -> int | None:
    if value is None:
        return None
    stripped = value.strip()
    return int(stripped) if stripped else None


@lru_cache(maxsize=32)
def _load_regions_for_root(resolved_root: Path) -> dict[str, dict[str, str]]:
    path = _reference_path("regions.csv", project_root=resolved_root)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {row["region_id"]: row for row in rows}


def load_regions(project_root: str | Path | None = None) -> dict[str, dict[str, str]]:
    return _load_regions_for_root(_resolve_root(project_root))


@lru_cache(maxsize=32)
def _load_aliases_for_root(resolved_root: Path) -> dict[tuple[str, str], dict[str, str]]:
    path = _reference_path("region_aliases.csv", project_root=resolved_root)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    aliases: dict[tuple[str, str], dict[str, str]] = {}
    for row in sorted(rows, key=lambda item: int(item["priority"])):
        aliases[(row["source_scope"], row["normalized_alias"])] = row
    return aliases


def load_aliases(
    project_root: str | Path | None = None,
) -> dict[tuple[str, str], dict[str, str]]:
    return _load_aliases_for_root(_resolve_root(project_root))


def clear_reference_caches() -> None:
    """Clear cached region and alias tables."""
    _load_regions_for_root.cache_clear()
    _load_aliases_for_root.cache_clear()


def resolve_region(
    value: object,
    *,
    source_scope: str = "all_sources",
    project_root: str | Path | None = None,
) -> RegionMatch:
    """Resolve one source province name to the 34-region canonical identity."""
    source_name = str(value)
    normalized = normalize_region_key(value)
    aliases = load_aliases(project_root=project_root)

    candidates = [(source_scope, normalized)]
    if source_scope != "all_sources":
        candidates.append(("all_sources", normalized))

    row = next((aliases[key] for key in candidates if key in aliases), None)
    if row is None:
        raise KeyError(
            f"Unknown ECADIN region alias: {source_name!r} "
            f"(normalized={normalized!r}, source_scope={source_scope!r})"
        )

    return RegionMatch(
        source_name=source_name,
        normalized_alias=normalized,
        region_id=row["region_id"],
        canonical_region_name=row["canonical_region_name"],
        mapping_type=row["mapping_type"],
        aggregation_rule=row["aggregation_rule"],
        effective_start_year=_parse_optional_year(row.get("effective_start_year")),
        effective_end_year=_parse_optional_year(row.get("effective_end_year")),
    )


def resolve_many(
    values: Iterable[object],
    *,
    source_scope: str = "all_sources",
    project_root: str | Path | None = None,
) -> list[RegionMatch]:
    return [
        resolve_region(value, source_scope=source_scope, project_root=project_root)
        for value in values
    ]
