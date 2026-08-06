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


def normalize_region_key(value: object) -> str:
    """Normalize punctuation, whitespace, and case for deterministic lookup."""
    text = unicodedata.normalize("NFKC", str(value))
    text = text.strip().upper()
    text = re.sub(r"[.\-_/]+", " ", text)
    return re.sub(r"\s+", " ", text)


def _reference_path(filename: str) -> Path:
    return PATHS.data / "reference" / filename


@lru_cache(maxsize=1)
def load_regions() -> dict[str, dict[str, str]]:
    path = _reference_path("regions.csv")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {row["region_id"]: row for row in rows}


@lru_cache(maxsize=1)
def load_aliases() -> dict[tuple[str, str], dict[str, str]]:
    path = _reference_path("region_aliases.csv")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    aliases: dict[tuple[str, str], dict[str, str]] = {}
    for row in sorted(rows, key=lambda item: int(item["priority"]), reverse=True):
        aliases[(row["source_scope"], row["normalized_alias"])] = row
    return aliases


def resolve_region(
    value: object,
    *,
    source_scope: str = "all_sources",
) -> RegionMatch:
    """Resolve one source province name to the 34-region canonical identity."""
    source_name = str(value)
    normalized = normalize_region_key(value)
    aliases = load_aliases()

    candidates = [
        (source_scope, normalized),
        ("all_sources", normalized),
        ("population_pdrb_and_modern_province_sources", normalized),
    ]
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
    )


def resolve_many(
    values: Iterable[object],
    *,
    source_scope: str = "all_sources",
) -> list[RegionMatch]:
    return [resolve_region(value, source_scope=source_scope) for value in values]
