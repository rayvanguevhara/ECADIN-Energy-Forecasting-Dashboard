from __future__ import annotations

import unittest
from decimal import Decimal

from ecadin_energy.data_processing.cleaning.annual_province_series import (
    ParsedAnnualProvinceFile,
)
from ecadin_energy.data_processing.cleaning.installed_capacity import (
    _build_quality_flags,
    _classify_total_difference,
    _parse_decimal,
)


class InstalledCapacityCleanerTest(unittest.TestCase):
    def test_parse_missing_markers(self) -> None:
        for value in ["", "-", "–", "—"]:
            self.assertIsNone(_parse_decimal(value, context="unit test"))

    def test_parse_numeric(self) -> None:
        self.assertEqual(
            _parse_decimal("123.45", context="unit test"),
            Decimal("123.45"),
        )

    def test_total_difference_classification(self) -> None:
        self.assertEqual(_classify_total_difference(Decimal("0")), "valid")
        self.assertEqual(
            _classify_total_difference(Decimal("0.04")),
            "valid_with_rounding_difference",
        )
        self.assertEqual(
            _classify_total_difference(Decimal("-9.00")),
            "warning_source_total_mismatch",
        )

    def test_generic_total_keeps_gwh_compatibility_alias(self) -> None:
        item = ParsedAnnualProvinceFile(
            path=__import__("pathlib").Path("example.csv"),
            year=2024,
            file_sha256="abc",
            source_rows=38,
            missing_source_names=(),
            reported_indonesia_total=Decimal("10.00"),
            values_by_region_id={},
            source_contributors_by_region_id={},
        )
        self.assertEqual(
            item.reported_indonesia_total_gwh,
            item.reported_indonesia_total,
        )

    def test_large_zero_base_jump_detection(self) -> None:
        canonical_rows = [
            {"region_id": "XX", "year": 2020, "installed_capacity_mw": "0.00"},
            {"region_id": "XX", "year": 2021, "installed_capacity_mw": "150.00"},
            {"region_id": "YY", "year": 2020, "installed_capacity_mw": "0.00"},
            {"region_id": "YY", "year": 2021, "installed_capacity_mw": "99.99"},
        ]
        flags = _build_quality_flags(canonical_rows, parsed_files=[])
        zero_jump_flags = [
            row for row in flags if row["issue_type"] == "large_zero_base_jump"
        ]
        self.assertEqual(len(zero_jump_flags), 1)
        self.assertEqual(zero_jump_flags[0]["region_id"], "XX")
        self.assertEqual(zero_jump_flags[0]["metric_value"], "150.00")


if __name__ == "__main__":
    unittest.main()
