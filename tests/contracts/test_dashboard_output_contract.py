from __future__ import annotations

import unittest
from pathlib import Path

import pandas as pd

from ecadin_energy.dashboard.validation import validate_dashboard_production
from ecadin_energy.pipeline.dashboard import run_dashboard_pipeline


class DashboardOutputContractTest(unittest.TestCase):
    def test_output_keys_and_contracts(self) -> None:
        root = Path(__file__).resolve().parents[2]
        run_dashboard_pipeline(project_root=root, run_frontend_build=False)
        detail = pd.read_csv(root / "outputs/dashboard/production/dashboard_province_detail.csv")
        self.assertFalse(detail.duplicated(["region_id", "year"]).any())
        checks = validate_dashboard_production(project_root=root)
        self.assertTrue(checks["passed"].all())


if __name__ == "__main__":
    unittest.main()
