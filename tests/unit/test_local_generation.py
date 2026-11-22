from __future__ import annotations

import shutil
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from ecadin_energy.data_processing.cleaning.local_generation import (
    _build_quality_flags,
    _classify_total_difference,
    _parse_decimal,
    validate_local_generation,
)
from ecadin_energy.data_processing.harmonization.regions import clear_reference_caches

SOURCE_ROOT = Path(__file__).resolve().parents[2]


class LocalGenerationCleanerTest(unittest.TestCase):
    def test_parse_missing_markers(self) -> None:
        for value in ["", "-", "–", "—"]:
            self.assertIsNone(_parse_decimal(value, context="unit test"))

    def test_parse_numeric(self) -> None:
        self.assertEqual(
            str(_parse_decimal("123.45", context="unit test")),
            "123.45",
        )

    def test_total_difference_classification(self) -> None:
        self.assertEqual(_classify_total_difference(Decimal("0")), "valid")
        self.assertEqual(
            _classify_total_difference(Decimal("0.05")),
            "valid_with_rounding_difference",
        )
        self.assertEqual(
            _classify_total_difference(Decimal("10.08")),
            "warning_source_total_mismatch",
        )

    def test_large_zero_base_jump_flagged_for_sr_2021(self) -> None:
        canonical_rows = [
            {"region_id": "SR", "year": 2020, "local_generation_gwh": "0.00"},
            {"region_id": "SR", "year": 2021, "local_generation_gwh": "249.45"},
            {"region_id": "YO", "year": 2021, "local_generation_gwh": "0.00"},
            {"region_id": "YO", "year": 2022, "local_generation_gwh": "50.00"},
        ]
        flags = _build_quality_flags(canonical_rows, parsed_files=[])
        zero_jump_flags = [
            row for row in flags if row["issue_type"] == "large_zero_base_jump"
        ]
        self.assertEqual(len(zero_jump_flags), 1)
        flag = zero_jump_flags[0]
        self.assertEqual(flag["region_id"], "SR")
        self.assertEqual(flag["year"], 2021)
        self.assertEqual(flag["observed_value"], "249.45")
        self.assertEqual(flag["comparison_value"], "0.00")
        self.assertEqual(flag["metric_value"], "249.45")

    def test_validate_local_generation_detects_raw_sha256_tampering(self) -> None:
        clear_reference_caches()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                shutil.copytree(
                    SOURCE_ROOT / "data/raw/bps/local_generation",
                    root / "data/raw/bps/local_generation",
                )
                for rel in (
                    "data/reference/regions.csv",
                    "data/processed/supply/local_generation.csv",
                    "data/processed/master/data_lineage.csv",
                    "data/processed/master/data_quality_flags.csv",
                    "outputs/reports/data/local_generation_build_summary.json",
                ):
                    dst = root / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(SOURCE_ROOT / rel, dst)

                result = validate_local_generation(project_root=root)
                self.assertEqual(result["status"], "valid")

                raw_sample = sorted((root / "data/raw/bps/local_generation").glob("*.csv"))[0]
                raw_sample.write_bytes(raw_sample.read_bytes() + b"\n")
                with self.assertRaisesRegex(ValueError, "Raw source SHA-256 mismatch"):
                    validate_local_generation(project_root=root)
        finally:
            clear_reference_caches()


if __name__ == "__main__":
    unittest.main()
