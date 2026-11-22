from __future__ import annotations

import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from ecadin_energy.dashboard.configuration import load_dashboard_config
from ecadin_energy.dashboard.national_overview import build_national_timeseries
from ecadin_energy.dashboard.region_detail import build_region_detail


class DashboardNationalTest(unittest.TestCase):
    def test_national_uses_complete_pairs_and_matched_yoy(self) -> None:
        root = Path(__file__).resolve().parents[2]
        config = load_dashboard_config(project_root=root)
        combined = pd.read_csv(
            root
            / "tests/fixtures/production/combined/"
            "regional_energy_history_forecast.csv"
        )
        regions = pd.read_csv(root / "data/reference/regions.csv")
        detail = build_region_detail(combined, regions, config)
        national = build_national_timeseries(detail, 34)

        self.assertEqual(len(national), 20)
        self.assertIn("yoy_common_regions", national.columns)
        self.assertIn("yoy_basis", national.columns)

        row_2011 = national.loc[national["year"].eq(2011)].iloc[0]
        self.assertEqual(int(row_2011["complete_regions"]), 31)
        self.assertAlmostEqual(float(row_2011["demand_gwh"]), 154547.91, places=6)
        self.assertTrue(pd.isna(row_2011["demand_growth_yoy_percent"]))
        self.assertTrue(pd.isna(row_2011["supply_growth_yoy_percent"]))
        self.assertTrue(pd.isna(row_2011["yoy_common_regions"]))
        self.assertEqual(row_2011["yoy_basis"], "first_year")

        # 2013: 31 -> 33 complete regions (+KI, +KU); matched YoY uses common=31.
        row_2013 = national.loc[national["year"].eq(2013)].iloc[0]
        self.assertEqual(int(row_2013["yoy_common_regions"]), 31)
        self.assertEqual(row_2013["yoy_basis"], "partial_overlap_matched")
        self.assertAlmostEqual(float(row_2013["demand_growth_yoy_percent"]), 7.908585, places=5)
        self.assertAlmostEqual(float(row_2013["supply_growth_yoy_percent"]), 8.463101, places=5)

        # 2015: 33 -> 34 complete regions (+YO); matched YoY uses common=33.
        row_2015 = national.loc[national["year"].eq(2015)].iloc[0]
        self.assertEqual(int(row_2015["yoy_common_regions"]), 33)
        self.assertEqual(row_2015["yoy_basis"], "partial_overlap_matched")
        self.assertAlmostEqual(float(row_2015["demand_growth_yoy_percent"]), 2.612310, places=5)
        self.assertAlmostEqual(float(row_2015["supply_growth_yoy_percent"]), 0.731464, places=5)

        # 2020: 34 -> 33 complete regions (-YO supply missing); matched YoY excludes YO in both years.
        row_2020 = national.loc[national["year"].eq(2020)].iloc[0]
        self.assertEqual(int(row_2020["yoy_common_regions"]), 33)
        self.assertEqual(row_2020["yoy_basis"], "partial_overlap_matched")
        self.assertAlmostEqual(float(row_2020["demand_growth_yoy_percent"]), -2.615737, places=5)
        self.assertAlmostEqual(float(row_2020["supply_growth_yoy_percent"]), -1.688445, places=5)

        # 2021: 33 -> 34 complete regions (+YO returns); matched YoY uses common=33.
        row_2021 = national.loc[national["year"].eq(2021)].iloc[0]
        self.assertEqual(int(row_2021["yoy_common_regions"]), 33)
        self.assertEqual(row_2021["yoy_basis"], "partial_overlap_matched")
        self.assertAlmostEqual(float(row_2021["demand_growth_yoy_percent"]), 6.767275, places=5)
        self.assertAlmostEqual(float(row_2021["supply_growth_yoy_percent"]), 7.695514, places=5)

        # Consecutive 34-region years use matched_complete_regions.
        for complete_year in (2016, 2017, 2018, 2019, 2022, 2023, 2024):
            row = national.loc[national["year"].eq(complete_year)].iloc[0]
            self.assertEqual(int(row["yoy_common_regions"]), 34)
            self.assertEqual(row["yoy_basis"], "matched_complete_regions")
            self.assertTrue(np.isfinite(float(row["demand_growth_yoy_percent"])))
            self.assertTrue(np.isfinite(float(row["supply_growth_yoy_percent"])))


if __name__ == "__main__":
    unittest.main()
