from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import shutil

from ecadin_energy.pipeline.production import run_production_pipeline


class ProductionForecastingPipelineTest(unittest.TestCase):
    def test_full_contract(self) -> None:
        project_root = Path(__file__).resolve().parents[2]
        result = run_production_pipeline(project_root=project_root)
        summary = result["summary"]
        self.assertEqual(summary["demand_forecast_rows"], 204)
        self.assertEqual(summary["supply_forecast_rows"], 204)
        self.assertEqual(summary["accounting_rows"], 204)
        self.assertEqual(summary["combined_rows"], 680)
        self.assertEqual(summary["historical_incomplete_differences"], 9)
        self.assertEqual(summary["forecast_incomplete_differences"], 0)
        self.assertEqual(summary["production_contracts_passed"], 6)


if __name__ == "__main__":
    unittest.main()
