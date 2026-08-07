from __future__ import annotations

import unittest

from ecadin_energy.pipeline.dashboard import run_dashboard_pipeline
from ecadin_energy.pipeline.full import run_full_pipeline
from tests.helpers.project_fixture import PortableProject


class FullPipelineTest(unittest.TestCase):
    def test_resume_from_forecast_on_portable_fixture(self) -> None:
        with PortableProject(seed_production=False) as root:
            summary = run_full_pipeline(
                project_root=root,
                start_at="forecast",
                run_frontend_production_build=False,
            )
            report = root / "outputs/reports/release/full_pipeline_latest.json"
            self.assertTrue(report.is_file())
        self.assertEqual(summary["status"], "completed")
        self.assertEqual(summary["stages_passed"], 5)
        self.assertEqual(summary["stages_total"], 5)

    def test_resume_from_frontend_validates_release(self) -> None:
        with PortableProject() as root:
            run_dashboard_pipeline(project_root=root, run_frontend_build=False)
            summary = run_full_pipeline(
                project_root=root,
                start_at="frontend",
                run_frontend_production_build=False,
            )
        self.assertEqual(summary["status"], "completed")
        self.assertEqual(summary["stages_passed"], 1)
        self.assertEqual(summary["stages_total"], 1)


if __name__ == "__main__":
    unittest.main()
