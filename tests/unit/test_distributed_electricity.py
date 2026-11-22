from __future__ import annotations

import csv
import shutil
import tempfile
import unittest
from pathlib import Path

from ecadin_energy.data_processing.cleaning.distributed_electricity import (
    _build_quality_flags,
    _parse_decimal,
    validate_distributed_electricity,
)
from ecadin_energy.data_processing.harmonization.regions import clear_reference_caches

SOURCE_ROOT = Path(__file__).resolve().parents[2]


class DistributedElectricityCleanerTest(unittest.TestCase):
    def test_parse_missing_markers(self) -> None:
        for value in ["", "-", "–", "—"]:
            self.assertIsNone(_parse_decimal(value, context="unit test"))

    def test_parse_numeric(self) -> None:
        self.assertEqual(str(_parse_decimal("123.45", context="unit test")), "123.45")

    def test_large_zero_base_jump_detection(self) -> None:
        canonical_rows = [
            {"region_id": "XX", "year": 2020, "distributed_electricity_gwh": "0.00"},
            {"region_id": "XX", "year": 2021, "distributed_electricity_gwh": "120.00"},
            {"region_id": "YY", "year": 2020, "distributed_electricity_gwh": "0.00"},
            {"region_id": "YY", "year": 2021, "distributed_electricity_gwh": "50.00"},
        ]
        flags = _build_quality_flags(canonical_rows)
        zero_jump_flags = [
            row for row in flags if row["issue_type"] == "large_zero_base_jump"
        ]
        self.assertEqual(len(zero_jump_flags), 1)
        self.assertEqual(zero_jump_flags[0]["region_id"], "XX")
        self.assertEqual(zero_jump_flags[0]["metric_value"], "120.00")

    def test_validate_distributed_electricity_enforces_yoy_flags_contract(self) -> None:
        clear_reference_caches()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                shutil.copytree(
                    SOURCE_ROOT / "data/raw/bps/distributed_electricity",
                    root / "data/raw/bps/distributed_electricity",
                )
                for rel in (
                    "data/reference/regions.csv",
                    "data/processed/demand/distributed_electricity.csv",
                    "data/processed/master/data_lineage.csv",
                    "data/processed/master/data_quality_flags.csv",
                    "outputs/reports/data/distributed_electricity_build_summary.json",
                ):
                    dst = root / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(SOURCE_ROOT / rel, dst)

                result = validate_distributed_electricity(project_root=root)
                self.assertEqual(result["large_yoy_warning_flags"], 7)

                flags_path = root / "data/processed/master/data_quality_flags.csv"
                with flags_path.open("r", encoding="utf-8-sig", newline="") as handle:
                    reader = csv.DictReader(handle)
                    fields = reader.fieldnames
                    rows = list(reader)
                dropped = False
                filtered = []
                for row in rows:
                    if (
                        not dropped
                        and row["dataset_id"] == "demand_distributed_electricity"
                        and row["issue_type"] == "large_consecutive_yoy_change"
                    ):
                        dropped = True
                        continue
                    filtered.append(row)
                with flags_path.open("w", encoding="utf-8-sig", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\r\n")
                    writer.writeheader()
                    writer.writerows(filtered)

                with self.assertRaisesRegex(ValueError, "YoY|Quality issue counts"):
                    validate_distributed_electricity(project_root=root)
        finally:
            clear_reference_caches()


if __name__ == "__main__":
    unittest.main()
