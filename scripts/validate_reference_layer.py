from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path


EXPECTED_REGION_COUNT = 34


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    reference = project_root / "data" / "reference"

    regions_path = reference / "regions.csv"
    aliases_path = reference / "region_aliases.csv"
    coordinates_path = reference / "region_coordinates.csv"
    variables_path = reference / "variable_dictionary.csv"
    contract_path = reference / "reference_layer_contract.json"

    paths = [
        regions_path,
        aliases_path,
        coordinates_path,
        variables_path,
        contract_path,
    ]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        print("[FAIL] Missing reference files:")
        for path in missing:
            print(f"  - {path}")
        return 1

    regions = read_csv(regions_path)
    aliases = read_csv(aliases_path)
    coordinates = read_csv(coordinates_path)
    contract = json.loads(contract_path.read_text(encoding="utf-8"))

    failures: list[str] = []

    region_ids = [row["region_id"] for row in regions]
    if len(regions) != EXPECTED_REGION_COUNT:
        failures.append(f"Expected 34 regions, found {len(regions)}.")
    if len(set(region_ids)) != len(region_ids):
        failures.append("Duplicate region_id detected.")
    if len(coordinates) != EXPECTED_REGION_COUNT:
        failures.append(f"Expected 34 coordinates, found {len(coordinates)}.")
    if set(region_ids) != {row["region_id"] for row in coordinates}:
        failures.append("Coordinate region set does not match regions.csv.")
    if any(not row["normalized_alias"] for row in aliases):
        failures.append("Blank normalized alias detected.")
    if any(row["region_id"] not in set(region_ids) for row in aliases):
        failures.append("Alias points to an unknown region_id.")

    alias_keys: dict[tuple[str, str], str] = {}
    for row in aliases:
        key = (row["source_scope"], row["normalized_alias"])
        previous = alias_keys.get(key)
        if previous is not None and previous != row["region_id"]:
            failures.append(f"Conflicting alias mapping: {key}.")
        alias_keys[key] = row["region_id"]

    for filename, expected_hash in contract["file_hashes"].items():
        actual = sha256_file(reference / filename)
        if actual != expected_hash:
            failures.append(f"SHA-256 mismatch for {filename}.")

    if failures:
        print("ECADIN REFERENCE LAYER VALIDATION: FAILED")
        for failure in failures:
            print(f"[FAIL] {failure}")
        return 1

    bubble_only = [
        row["canonical_region_name"]
        for row in regions
        if row["geometry_status"] == "bubble_only"
    ]
    print("ECADIN REFERENCE LAYER VALIDATION: PASSED")
    print(f"Regions       : {len(regions)}")
    print(f"Aliases       : {len(aliases)}")
    print(f"Coordinates   : {len(coordinates)}")
    print(f"Bubble-only   : {', '.join(bubble_only)}")
    print("Canonical key : region_id + year")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
