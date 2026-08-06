from __future__ import annotations

import unittest
from pathlib import Path

from ecadin_energy.pipeline.dashboard import run_dashboard_pipeline


class DashboardPipelineTest(unittest.TestCase):
    def test_full_dashboard_pipeline_without_frontend_build(self) -> None:
        root = Path(__file__).resolve().parents[2]
        result = run_dashboard_pipeline(project_root=root, run_frontend_build=False)
        self.assertEqual(result["staging"]["region_rows"], 680)
        self.assertTrue(result["production_checks"]["passed"].all())
        self.assertEqual(result["frontend"]["nondata_files_changed"], [])


if __name__ == "__main__":
    unittest.main()
