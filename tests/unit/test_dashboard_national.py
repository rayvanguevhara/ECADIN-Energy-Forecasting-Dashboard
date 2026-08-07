from __future__ import annotations

import unittest
from pathlib import Path

import pandas as pd

from ecadin_energy.dashboard.configuration import load_dashboard_config
from ecadin_energy.dashboard.national_overview import build_national_timeseries
from ecadin_energy.dashboard.region_detail import build_region_detail


class DashboardNationalTest(unittest.TestCase):
    def test_national_uses_complete_pairs(self) -> None:
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
        row = national.loc[national["year"].eq(2011)].iloc[0]
        self.assertEqual(int(row["complete_regions"]), 31)
        self.assertAlmostEqual(float(row["demand_gwh"]), 154547.91, places=6)
        self.assertEqual(len(national), 20)


if __name__ == "__main__":
    unittest.main()
