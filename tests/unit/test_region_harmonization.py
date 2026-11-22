from __future__ import annotations

import csv
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from ecadin_energy.data_processing.harmonization.regions import (
    clear_reference_caches,
    load_aliases,
    load_regions,
    resolve_many,
    resolve_region,
)
from ecadin_energy.data_processing.reference import validate_reference_layer

SOURCE_REFERENCE = Path(__file__).resolve().parents[2] / "data" / "reference"

REGION_FIELDS = [
    "region_id",
    "bps_code",
    "canonical_region_name",
    "display_name",
    "island_group",
    "modeling_order",
    "geometry_status",
    "first_observed_demand_year",
    "first_observed_supply_year",
    "notes",
]

ALIAS_FIELDS = [
    "alias_id",
    "source_scope",
    "source_region_name",
    "normalized_alias",
    "region_id",
    "canonical_region_name",
    "mapping_type",
    "aggregation_rule",
    "included_as_separate_model_region",
    "priority",
    "effective_start_year",
    "effective_end_year",
    "notes",
]


def _write_reference_tables(
    root: Path,
    *,
    regions: list[dict[str, str]],
    aliases: list[dict[str, str]],
) -> None:
    ref_dir = root / "data" / "reference"
    ref_dir.mkdir(parents=True, exist_ok=True)
    with (ref_dir / "regions.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REGION_FIELDS, lineterminator="\r\n")
        writer.writeheader()
        writer.writerows(regions)
    with (ref_dir / "region_aliases.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=ALIAS_FIELDS, lineterminator="\r\n")
        writer.writeheader()
        writer.writerows(aliases)


def _region_row(region_id: str, name: str, order: int = 1) -> dict[str, str]:
    return {
        "region_id": region_id,
        "bps_code": "11",
        "canonical_region_name": name,
        "display_name": name.title(),
        "island_group": "Test",
        "modeling_order": str(order),
        "geometry_status": "polygon",
        "first_observed_demand_year": "2011",
        "first_observed_supply_year": "2011",
        "notes": "",
    }


def _alias_row(
    alias_id: str,
    *,
    source_scope: str,
    source_region_name: str,
    normalized_alias: str,
    region_id: str,
    canonical_region_name: str,
    mapping_type: str = "identity",
    aggregation_rule: str = "none",
    included: str = "True",
    priority: int = 100,
) -> dict[str, str]:
    return {
        "alias_id": alias_id,
        "source_scope": source_scope,
        "source_region_name": source_region_name,
        "normalized_alias": normalized_alias,
        "region_id": region_id,
        "canonical_region_name": canonical_region_name,
        "mapping_type": mapping_type,
        "aggregation_rule": aggregation_rule,
        "included_as_separate_model_region": included,
        "priority": str(priority),
        "effective_start_year": "",
        "effective_end_year": "",
        "notes": "",
    }


class RegionHarmonizationTest(unittest.TestCase):
    def tearDown(self) -> None:
        clear_reference_caches()

    def test_project_root_isolation(self) -> None:
        clear_reference_caches()
        with tempfile.TemporaryDirectory() as dir_a, tempfile.TemporaryDirectory() as dir_b:
            root_a = Path(dir_a)
            root_b = Path(dir_b)
            _write_reference_tables(
                root_a,
                regions=[_region_row("XX", "ALPHA REGION", order=1)],
                aliases=[
                    _alias_row(
                        "T001",
                        source_scope="all_sources",
                        source_region_name="SHARED NAME",
                        normalized_alias="SHARED NAME",
                        region_id="XX",
                        canonical_region_name="ALPHA REGION",
                    )
                ],
            )
            _write_reference_tables(
                root_b,
                regions=[_region_row("YY", "BETA REGION", order=1)],
                aliases=[
                    _alias_row(
                        "T001",
                        source_scope="all_sources",
                        source_region_name="SHARED NAME",
                        normalized_alias="SHARED NAME",
                        region_id="YY",
                        canonical_region_name="BETA REGION",
                    )
                ],
            )

            self.assertEqual(set(load_regions(project_root=root_a)), {"XX"})
            self.assertEqual(set(load_regions(project_root=root_b)), {"YY"})
            self.assertEqual(
                load_aliases(project_root=root_a)[("all_sources", "SHARED NAME")]["region_id"],
                "XX",
            )
            self.assertEqual(
                resolve_region("Shared Name", project_root=root_a).region_id,
                "XX",
            )
            self.assertEqual(
                [m.region_id for m in resolve_many(["Shared Name"], project_root=root_b)],
                ["YY"],
            )

    def test_alias_priority_higher_wins(self) -> None:
        clear_reference_caches()
        low = _alias_row(
            "T001",
            source_scope="all_sources",
            source_region_name="AMBIGUOUS PROV",
            normalized_alias="AMBIGUOUS PROV",
            region_id="LO",
            canonical_region_name="LOW PRIO",
            priority=50,
        )
        high = _alias_row(
            "T002",
            source_scope="all_sources",
            source_region_name="AMBIGUOUS PROV",
            normalized_alias="AMBIGUOUS PROV",
            region_id="HI",
            canonical_region_name="HIGH PRIO",
            priority=95,
        )
        regions = [
            _region_row("LO", "LOW PRIO", order=1),
            _region_row("HI", "HIGH PRIO", order=2),
        ]

        for order_name, alias_order in (("low_first", [low, high]), ("high_first", [high, low])):
            with self.subTest(order=order_name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                _write_reference_tables(root, regions=regions, aliases=alias_order)
                match = resolve_region("Ambiguous Prov", project_root=root)
                self.assertEqual(match.region_id, "HI")

    def test_resolve_region_all_sources_does_not_fallback_to_modern_scope(self) -> None:
        with self.assertRaises(KeyError):
            resolve_region("PAPUA SELATAN", source_scope="all_sources")

        match = resolve_region(
            "PAPUA SELATAN",
            source_scope="population_pdrb_and_modern_province_sources",
        )
        self.assertEqual(match.region_id, "PA")
        self.assertEqual(match.aggregation_rule, "sum_by_region_id_year")

    def test_a049_papua_baratdaya_aggregation_rule(self) -> None:
        match = resolve_region("PAPUA BARATDAYA", source_scope="all_sources")
        self.assertEqual(match.region_id, "PB")
        self.assertEqual(match.mapping_type, "aggregate_to_model_region")
        self.assertEqual(match.aggregation_rule, "sum_by_region_id_year")

    def test_validate_reference_layer_rejects_duplicate_alias_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ref_dir = root / "data" / "reference"
            ref_dir.mkdir(parents=True, exist_ok=True)
            for name in (
                "regions.csv",
                "region_aliases.csv",
                "region_coordinates.csv",
                "variable_dictionary.csv",
                "reference_layer_contract.json",
            ):
                shutil.copy2(SOURCE_REFERENCE / name, ref_dir / name)

            aliases_path = ref_dir / "region_aliases.csv"
            with aliases_path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                fields = reader.fieldnames
                rows = list(reader)

            dup = dict(rows[0])
            dup["alias_id"] = "A999"
            rows.append(dup)
            with aliases_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\r\n")
                writer.writeheader()
                writer.writerows(rows)

            contract_path = ref_dir / "reference_layer_contract.json"
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            contract["file_hashes"]["region_aliases.csv"] = hashlib.sha256(
                aliases_path.read_bytes()
            ).hexdigest()
            contract["alias_count"] = len(rows)
            contract_path.write_text(
                json.dumps(contract, indent=2) + "\n", encoding="utf-8"
            )

            with self.assertRaisesRegex(ValueError, "Duplicate alias key detected"):
                validate_reference_layer(project_root=root)


if __name__ == "__main__":
    unittest.main()
