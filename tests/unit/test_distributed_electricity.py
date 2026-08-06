from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from ecadin_energy.data_processing.cleaning.distributed_electricity import (
    _parse_decimal,
    validate_distributed_electricity,
)


class DistributedElectricityCleanerTest(unittest.TestCase):
    def test_parse_missing_markers(self) -> None:
        for value in ["", "-", "–", "—"]:
            self.assertIsNone(_parse_decimal(value, context="unit test"))

    def test_parse_numeric(self) -> None:
        self.assertEqual(str(_parse_decimal("123.45", context="unit test")), "123.45")


if __name__ == "__main__":
    unittest.main()
