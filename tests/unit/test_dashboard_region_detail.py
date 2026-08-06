from __future__ import annotations

import unittest
from pathlib import Path

import pandas as pd

from ecadin_energy.dashboard.configuration import load_dashboard_config
from ecadin_energy.dashboard.region_detail import build_region_detail, classify_accounting_difference


class DashboardRegionDetailTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[2]
        cls.config = load_dashboard_config(project_root=cls.root)

    def test_category_boundaries(self) -> None:
        self.assertEqual(classify_accounting_difference(20.0, self.config), "surplus_tinggi")
        self.assertEqual(classify_accounting_difference(5.0, self.config), "surplus_moderat")
        self.assertEqual(classify_accounting_difference(-5.0, self.config), "defisit_moderat")
        self.assertEqual(classify_accounting_difference(-20.0, self.config), "defisit_tinggi")
        self.assertEqual(classify_accounting_difference(None, self.config), "tidak_tersedia")

    def test_detail_contract(self) -> None:
        combined = pd.read_csv(self.root / "outputs/production/combined/regional_energy_history_forecast.csv")
        regions = pd.read_csv(self.root / "data/reference/regions.csv")
        detail = build_region_detail(combined, regions, self.config)
        self.assertEqual(len(detail), 680)
        self.assertEqual(detail["region_id"].nunique(), 34)
        self.assertEqual(int(detail["available"].sum()), 671)
        self.assertEqual(int((detail["quality"] == "interpolated").sum()), 34)
        self.assertTrue(detail["population_jiwa"].isna().all())


if __name__ == "__main__":
    unittest.main()
