from __future__ import annotations

import json
import unittest

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


if __name__ == "__main__":
    unittest.main()
