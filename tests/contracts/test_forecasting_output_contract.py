from __future__ import annotations

import unittest
from pathlib import Path

import pandas as pd


class ForecastingOutputContractTest(unittest.TestCase):
    def test_written_output_keys(self) -> None:
        root = Path(__file__).resolve().parents[2]
        demand = pd.read_csv(
            root / "outputs/production/forecasts/demand_forecast.csv"
        )
        supply = pd.read_csv(
            root / "outputs/production/forecasts/supply_forecast.csv"
        )
        self.assertFalse(demand.duplicated(["region_id", "year"]).any())
        self.assertFalse(supply.duplicated(["region_id", "year"]).any())
        self.assertEqual(demand["region_id"].nunique(), 34)
        self.assertEqual(supply["region_id"].nunique(), 34)
        self.assertEqual(sorted(demand["year"].unique()), list(range(2025, 2031)))


if __name__ == "__main__":
    unittest.main()
