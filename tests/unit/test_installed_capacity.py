from __future__ import annotations

import unittest
from decimal import Decimal

from ecadin_energy.data_processing.cleaning.annual_province_series import (
    ParsedAnnualProvinceFile,
)
from ecadin_energy.data_processing.cleaning.installed_capacity import (
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


if __name__ == "__main__":
    unittest.main()
