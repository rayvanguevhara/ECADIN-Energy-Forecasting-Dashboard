from __future__ import annotations

import json
import unittest

from ecadin_energy.dashboard.region_detail import VALID_GAP_CATEGORIES
from ecadin_energy.dashboard.staging import build_dashboard_staging
from tests.helpers.project_fixture import PortableProject


class DashboardFrontendPayloadTest(unittest.TestCase):
    def test_payload_contract_and_nulls(self) -> None:
        with PortableProject() as root:
            build_dashboard_staging(project_root=root)
            payload = json.loads(
                (
                    root
                    / "outputs/dashboard/staging/dashboard-production.json"
                ).read_text(encoding="utf-8")
            )
        self.assertEqual(payload["row_count"], 680)
        self.assertEqual(payload["region_count"], 34)
        self.assertEqual(len(payload["national"]), 20)
        points = [
            point
            for province in payload["provinces"]
            for point in province["series"]
        ]
        self.assertEqual(sum(not point["available"] for point in points), 9)
        self.assertTrue(
            all(
                point["gap_gwh"] is None
                for point in points
                if not point["available"]
            )
        )
        self.assertTrue(
            all(point["population_jiwa"] is None for point in points)
        )
        self.assertTrue(
            all(point["gap_category"] in VALID_GAP_CATEGORIES for point in points)
        )
        for nat_row in payload["national"]:
            self.assertIn("yoy_common_regions", nat_row)
            self.assertIn("yoy_basis", nat_row)
        self.assertIn("quality_flags_total", payload)
        self.assertIn("quality_flags_summary", payload)
        self.assertIn("quality_flags_highlights", payload)
        self.assertIn("methodology", payload)
        self.assertIn("legacy_ridge_clarification", payload)
        for model_row in payload["models"]:
            self.assertIn("rolling_macro_smape_percent", model_row)
            self.assertIn("recursive_macro_smape_percent", model_row)
            self.assertIn("evaluated_backtest_model_count", model_row)


if __name__ == "__main__":
    unittest.main()
