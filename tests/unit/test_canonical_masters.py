from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from ecadin_energy.data_processing.mastering.canonical_masters import (
    _load_unique_index,
    _validate_numeric_text,
)


class CanonicalMastersTest(unittest.TestCase):
    def test_unique_index_accepts_blank_value(self) -> None:
        content = (
            "region_id,year,value\n"
            "AC,2016,\n"
            "AC,2017,1.25\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.csv"
            path.write_text(content, encoding="utf-8")
            index = _load_unique_index(
                path,
                key_fields=("region_id", "year"),
                required_value_fields=("value",),
            )
        self.assertEqual(index[("AC", "2016")]["value"], "")
        self.assertEqual(index[("AC", "2017")]["value"], "1.25")

    def test_unique_index_rejects_duplicate_key(self) -> None:
        content = (
            "region_id,year,value\n"
            "AC,2017,1\n"
            "AC,2017,2\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.csv"
            path.write_text(content, encoding="utf-8")
            with self.assertRaises(ValueError):
                _load_unique_index(
                    path,
                    key_fields=("region_id", "year"),
                    required_value_fields=("value",),
                )

    def test_numeric_validation_accepts_blank_and_zero(self) -> None:
        _validate_numeric_text("", context="test")
        _validate_numeric_text("0", context="test")
        _validate_numeric_text("1.25", context="test")

    def test_numeric_validation_rejects_negative(self) -> None:
        with self.assertRaises(ValueError):
            _validate_numeric_text("-1", context="test")

    def test_integer_validation_rejects_fractional_count(self) -> None:
        with self.assertRaises(ValueError):
            _validate_numeric_text(
                "1.5",
                integer_only=True,
                context="test",
            )


if __name__ == "__main__":
    unittest.main()
