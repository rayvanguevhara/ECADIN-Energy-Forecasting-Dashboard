from __future__ import annotations

import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from ecadin_energy.data_processing.cleaning.electricity_customers import (
    _classify_total_difference,
    _format_count,
    _read_source_file,
)


class ElectricityCustomersCleanerTest(unittest.TestCase):
    def test_total_difference_requires_exact_reconciliation(self) -> None:
        self.assertEqual(_classify_total_difference(Decimal("0")), "valid")
        self.assertEqual(
            _classify_total_difference(Decimal("1")),
            "warning_source_total_mismatch",
        )

    def test_format_count_preserves_integer(self) -> None:
        self.assertEqual(_format_count(Decimal("92877292")), "92877292")
        self.assertEqual(_format_count(None), "")

    def test_format_count_rejects_fractional_value(self) -> None:
        with self.assertRaises(ValueError):
            _format_count(Decimal("1.5"))

    def test_source_parser_normalizes_business_typo(self) -> None:
        content = (
            "Customer Group,\n"
            ",Customers of Electricity State Company\n"
            ",2024\n"
            "Social,1\n"
            "Households,2\n"
            "Bussiness,3\n"
            "Industry,4\n"
            "Public,5\n"
            "All Customer,15\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / (
                "Customers of Electricity State Company, 2024.csv"
            )
            path.write_text(content, encoding="utf-8")
            parsed = _read_source_file(path)
        self.assertEqual(parsed.values_by_category_id["business"], Decimal("3"))
        self.assertEqual(parsed.reported_total, Decimal("15"))

    def test_source_parser_rejects_fractional_count(self) -> None:
        content = (
            "Customer Group,\n"
            ",Customers of Electricity State Company\n"
            ",2024\n"
            "Social,1.5\n"
            "Households,2\n"
            "Bussiness,3\n"
            "Industry,4\n"
            "Public,5\n"
            "All Customer,15.5\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / (
                "Customers of Electricity State Company, 2024.csv"
            )
            path.write_text(content, encoding="utf-8")
            with self.assertRaises(ValueError):
                _read_source_file(path)


if __name__ == "__main__":
    unittest.main()
