from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from ecadin_energy.data_processing.cleaning.distributed_electricity import (
    _build_quality_flags,
    _parse_decimal,
    validate_distributed_electricity,
)


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


if __name__ == "__main__":
    unittest.main()
