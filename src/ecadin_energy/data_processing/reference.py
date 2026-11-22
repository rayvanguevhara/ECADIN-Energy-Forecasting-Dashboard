from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from ecadin_energy.config import PATHS


EXPECTED_REGION_COUNT = 34
EXPECTED_CUSTOMER_GROUP_COUNT = 5
REQUIRED_HASHED_FILES = (
    "regions.csv",
    "region_aliases.csv",
    "region_coordinates.csv",
    "variable_dictionary.csv",
    "customer_groups.csv",
    "source_registry.csv",
)


def _root(project_root: str | Path | None) -> Path:
    return Path(project_root).resolve() if project_root else PATHS.root


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def validate_reference_layer(
    *,
    project_root: str | Path | None = None,
) -> dict[str, Any]:
    root = _root(project_root)
    reference = root / "data/reference"

    regions_path = reference / "regions.csv"
    aliases_path = reference / "region_aliases.csv"
    coordinates_path = reference / "region_coordinates.csv"
    variables_path = reference / "variable_dictionary.csv"
    customer_groups_path = reference / "customer_groups.csv"
    source_registry_path = reference / "source_registry.csv"
    contract_path = reference / "reference_layer_contract.json"

    paths = [
        regions_path,
        aliases_path,
        coordinates_path,
        variables_path,
        customer_groups_path,
        source_registry_path,
        contract_path,
    ]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "Reference files are missing:\n- " + "\n- ".join(missing)
        )

    regions = _read_csv(regions_path)
    aliases = _read_csv(aliases_path)
    coordinates = _read_csv(coordinates_path)
    customer_groups = _read_csv(customer_groups_path)
    source_registry = _read_csv(source_registry_path)
    contract = json.loads(contract_path.read_text(encoding="utf-8"))

    failures: list[str] = []
    region_ids = [row["region_id"] for row in regions]
    region_id_set = set(region_ids)

    if len(regions) != EXPECTED_REGION_COUNT:
        failures.append(
            f"Expected {EXPECTED_REGION_COUNT} regions, found {len(regions)}."
        )
    if len(region_id_set) != len(region_ids):
        failures.append("Duplicate region_id detected.")
    if len(coordinates) != EXPECTED_REGION_COUNT:
        failures.append(
            f"Expected {EXPECTED_REGION_COUNT} coordinates, found {len(coordinates)}."
        )
    if region_id_set != {row["region_id"] for row in coordinates}:
        failures.append("Coordinate region set does not match regions.csv.")

    group_ids = [row.get("customer_group_id", "").strip() for row in customer_groups]
    if len(customer_groups) != EXPECTED_CUSTOMER_GROUP_COUNT or len(set(group_ids)) != len(group_ids):
        failures.append(
            f"Expected {EXPECTED_CUSTOMER_GROUP_COUNT} unique customer groups in customer_groups.csv."
        )
    if any(
        not row.get("customer_group_id", "").strip()
        or not row.get("modeling_order", "").strip()
        or not row.get("source_label", "").strip()
        for row in customer_groups
    ):
        failures.append("Blank customer group field detected in customer_groups.csv.")

    dataset_ids = [row.get("dataset_id", "").strip() for row in source_registry]
    if not source_registry or any(not d for d in dataset_ids) or len(set(dataset_ids)) != len(dataset_ids):
        failures.append("source_registry.csv must contain unique non-blank dataset_id rows.")

    if any(not row["normalized_alias"] for row in aliases):
        failures.append("Blank normalized alias detected.")
    if any(row["region_id"] not in region_id_set for row in aliases):
        failures.append("Alias points to an unknown region_id.")

    alias_keys: dict[tuple[str, str], str] = {}
    for row in aliases:
        key = (row["source_scope"], row["normalized_alias"])
        previous = alias_keys.get(key)
        if previous is not None:
            if previous != row["region_id"]:
                failures.append(f"Conflicting alias mapping: {key}.")
            else:
                failures.append(f"Duplicate alias key detected: {key}.")
        alias_keys[key] = row["region_id"]

    expected_alias_count = contract.get("alias_count")
    if expected_alias_count is not None and len(aliases) != int(expected_alias_count):
        failures.append(
            f"Expected {expected_alias_count} aliases, found {len(aliases)}."
        )

    file_hashes = contract.get("file_hashes", {})
    missing_hashes = [name for name in REQUIRED_HASHED_FILES if name not in file_hashes]
    if missing_hashes:
        failures.append(
            f"reference_layer_contract.json is missing hashes for: {missing_hashes}."
        )
    for filename, expected_hash in file_hashes.items():
        target = reference / filename
        if not target.is_file():
            failures.append(f"Hashed reference file is missing: {filename}.")
            continue
        actual = sha256_file(target)
        if actual != expected_hash:
            failures.append(f"SHA-256 mismatch for {filename}.")

    if failures:
        raise ValueError(
            "Reference layer validation failed:\n- " + "\n- ".join(failures)
        )

    bubble_only = [
        row["canonical_region_name"]
        for row in regions
        if row["geometry_status"] == "bubble_only"
    ]
    return {
        "regions": len(regions),
        "aliases": len(aliases),
        "coordinates": len(coordinates),
        "customer_groups": len(customer_groups),
        "source_registry_entries": len(source_registry),
        "hashed_files": len(file_hashes),
        "bubble_only": bubble_only,
        "canonical_key": "region_id + year",
    }
