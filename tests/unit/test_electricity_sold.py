from __future__ import annotations

import csv
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from ecadin_energy.data_processing.cleaning.annual_category_series import (
    read_annual_category_file,
)
from ecadin_energy.data_processing.cleaning.electricity_sold import (
    _classify_total_difference,
)


class ElectricitySoldCleanerTest(unittest.TestCase):
    def test_total_difference_classification(self) -> None:
        self.assertEqual(_classify_total_difference(Decimal("0")), "valid")
        self.assertEqual(
            _classify_total_difference(Decimal("0.01")),
            "valid_with_rounding_difference",
        )
        self.assertEqual(
            _classify_total_difference(Decimal("0.02")),
            "warning_source_total_mismatch",
        )

    def test_category_parser_normalizes_business_source_typo(self) -> None:
        content = (
            "Customer Group,\n"
            ",Electricity Sold (GWh)\n"
            ",2024\n"
            "Social,1\n"
            "Households,2\n"
            "Bussiness,3\n"
            "Industry,4\n"
            "Public,5\n"
            "All Customer,15\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "Electricity Sold, 2024.csv"
            path.write_text(content, encoding="utf-8")
            parsed = read_annual_category_file(
                path,
                source_label_to_category_id={
                    "Social": "social",
                    "Households": "households",
                    "Bussiness": "business",
                    "Industry": "industry",
                    "Public": "public",
                },
                total_source_label="All Customer",
            )
        self.assertEqual(parsed.values_by_category_id["business"], Decimal("3"))
        self.assertEqual(parsed.reported_total, Decimal("15"))

    def test_category_parser_rejects_unknown_label(self) -> None:
        content = (
            "Customer Group,\n"
            ",Electricity Sold (GWh)\n"
            ",2024\n"
            "Unknown,1\n"
            "All Customer,1\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "Electricity Sold, 2024.csv"
            path.write_text(content, encoding="utf-8")
            with self.assertRaises(ValueError):
                read_annual_category_file(
                    path,
                    source_label_to_category_id={"Social": "social"},
                    total_source_label="All Customer",
                )


if __name__ == "__main__":
    unittest.main()
