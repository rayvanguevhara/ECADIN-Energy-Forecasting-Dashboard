from __future__ import annotations

import unittest
from decimal import Decimal

from ecadin_energy.data_processing.cleaning.local_generation import (
    _classify_total_difference,
    _parse_decimal,
)


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


if __name__ == "__main__":
    unittest.main()
