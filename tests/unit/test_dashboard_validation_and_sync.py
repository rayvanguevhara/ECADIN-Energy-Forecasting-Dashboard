from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

from ecadin_energy.dashboard.configuration import load_dashboard_config
from ecadin_energy.dashboard.contracts import DashboardContractError
from ecadin_energy.dashboard.data_quality import (
    build_quality_flags_highlights,
    build_quality_flags_summary,
)
from ecadin_energy.dashboard.frontend_refresh import refresh_frontend_data
from ecadin_energy.dashboard.methodology import build_methodology, frontend_metadata
from ecadin_energy.dashboard.production_models import build_model_summary
from ecadin_energy.dashboard.serializers import sha256_file, write_csv
from ecadin_energy.dashboard.staging import OUTPUT_HASH_MANIFEST_FILE
from ecadin_energy.dashboard.validation import validate_dashboard_production
from ecadin_energy.forecasting.configuration import load_production_config
from ecadin_energy.pipeline.dashboard import run_dashboard_pipeline
from ecadin_energy.pipeline.full import run_full_pipeline
from ecadin_energy.pipeline.release import run_frontend_build, validate_frontend_release
from tests.helpers.project_fixture import PortableProject


SOURCE_ROOT = Path(__file__).resolve().parents[2]


def _rehash_manifest_entry(directory: Path, relative_path: str) -> None:
    manifest_path = directory / OUTPUT_HASH_MANIFEST_FILE
    manifest = pd.read_csv(manifest_path, low_memory=False)
    target = directory / relative_path
    mask = manifest["relative_path"].astype(str).eq(relative_path)
    manifest.loc[mask, "size_bytes"] = target.stat().st_size
    manifest.loc[mask, "sha256"] = sha256_file(target)
    write_csv(manifest, manifest_path)


class DashboardValidationAndSyncTest(unittest.TestCase):
    def test_v2_model_metrics_methodology_and_quality_flags_sync(self) -> None:
        dash_cfg = load_dashboard_config(project_root=SOURCE_ROOT)
        fc_cfg = load_production_config(project_root=SOURCE_ROOT)
        raw_models = pd.read_csv(
            SOURCE_ROOT / "outputs/production/metrics/production_model_summary.csv"
        )
        raw_flags = pd.read_csv(
            SOURCE_ROOT / "data/processed/master/data_quality_flags.csv",
            low_memory=False,
        )
        regions = pd.read_csv(SOURCE_ROOT / "data/reference/regions.csv")

        summary_models = build_model_summary(
            raw_models, dash_cfg, forecast_config=fc_cfg
        )
        demand_row = summary_models.loc[summary_models["side"].eq("demand")].iloc[0]
        supply_row = summary_models.loc[summary_models["side"].eq("supply")].iloc[0]

        self.assertEqual(demand_row["model_version"], "demand_production_drift")
        self.assertEqual(int(demand_row["evaluated_backtest_model_count"]), 4)
        self.assertAlmostEqual(float(demand_row["rolling_macro_smape_percent"]), 5.834758, places=4)
        self.assertAlmostEqual(float(demand_row["recursive_macro_smape_percent"]), 8.135140, places=4)
        self.assertTrue(pd.isna(demand_row["break_year"]))

        self.assertEqual(supply_row["active_model"], "national_reconciled_supply")
        self.assertEqual(
            supply_row["model_version"], "supply_production_national_reconciled_v2"
        )
        self.assertEqual(int(supply_row["evaluated_backtest_model_count"]), 5)
        self.assertAlmostEqual(float(supply_row["rolling_macro_smape_percent"]), 29.045031, places=4)
        self.assertAlmostEqual(float(supply_row["recursive_macro_smape_percent"]), 54.521623, places=4)
        self.assertEqual(int(supply_row["break_year"]), 2021)
        self.assertAlmostEqual(float(supply_row["ridge_lambda"]), 25.0, places=6)
        self.assertAlmostEqual(float(supply_row["damping_phi"]), 0.85, places=6)
        self.assertEqual(int(supply_row["national_start_year"]), 2013)

        methodology = build_methodology(
            dash_cfg, models=summary_models, forecast_config=fc_cfg
        )
        metadata, metadata_v2 = frontend_metadata(
            dash_cfg, models=summary_models, forecast_config=fc_cfg
        )
        serialized = json.dumps({"m": methodology, "l": metadata, "v2": metadata_v2})
        self.assertNotIn("Drift V1", serialized)
        self.assertNotIn("supply_production_drift_v1", serialized)
        self.assertEqual(methodology["phase2_benchmark_summary"]["total_evaluated_models"], 26)
        self.assertEqual(methodology["adr_001_data_governance"]["reference"], "ADR-001")
        self.assertEqual(methodology["uncertainty_calibration_k3"]["log_shift_gwh"], 10.0)
        self.assertIn("lambda=25.0", serialized)
        self.assertFalse(methodology["contract_clarifications"]["legacy_ridge_used"]["value"])
        self.assertEqual(
            metadata_v2["supply_model"], "supply_production_national_reconciled_v2"
        )
        self.assertEqual(metadata_v2["supply_break_year"], "2021")

        flags_summary = build_quality_flags_summary(raw_flags)
        flags_highlights = build_quality_flags_highlights(raw_flags, regions)
        self.assertEqual(int(flags_summary["flag_count"].sum()), 191)
        sr_2021 = flags_highlights.loc[
            flags_highlights["region_id"].eq("SR")
            & flags_highlights["year"].eq(2021)
            & flags_highlights["issue_type"].eq("large_zero_base_jump")
        ]
        self.assertEqual(len(sr_2021), 1)
        kr_2020 = flags_highlights.loc[
            flags_highlights["region_id"].eq("KR") & flags_highlights["year"].eq(2020)
        ]
        self.assertEqual(len(kr_2020), 1)
        self.assertAlmostEqual(float(kr_2020.iloc[0]["metric_value"]), -73.48, places=2)

    def test_sha256_tamper_and_cross_consistency_detection(self) -> None:
        with PortableProject() as root:
            run_dashboard_pipeline(project_root=root, run_frontend_build=False)
            prod_dir = root / "outputs/dashboard/production"
            checks = validate_dashboard_production(project_root=root)
            self.assertEqual(len(checks), 13)
            self.assertTrue(checks["passed"].all())

            # 1. Tamper deterministic output file -> output_hashes_sha256 fails.
            detail_path = prod_dir / "dashboard_province_detail.csv"
            original_detail = detail_path.read_bytes()
            detail_path.write_bytes(original_detail + b"\n")
            with self.assertRaises(DashboardContractError) as err1:
                validate_dashboard_production(project_root=root)
            self.assertIn("output_hashes_sha256", str(err1.exception))
            detail_path.write_bytes(original_detail)

            # 2. Tamper upstream input file -> input_hashes_sha256 fails.
            regions_path = root / "data/reference/regions.csv"
            original_regions = regions_path.read_bytes()
            regions_path.write_bytes(original_regions + b" ")
            with self.assertRaises(DashboardContractError) as err2:
                validate_dashboard_production(project_root=root)
            self.assertIn("input_hashes_sha256", str(err2.exception))
            regions_path.write_bytes(original_regions)

            # 3. Cross-consistency check even if manifest is rehashed: mutate national demand.
            nat_path = prod_dir / "dashboard_national_timeseries.csv"
            original_nat = nat_path.read_bytes()
            original_manifest = (prod_dir / OUTPUT_HASH_MANIFEST_FILE).read_bytes()
            nat_df = pd.read_csv(nat_path)
            nat_df.loc[nat_df["year"].eq(2024), "demand_gwh"] += 500.0
            write_csv(nat_df, nat_path)
            _rehash_manifest_entry(prod_dir, "dashboard_national_timeseries.csv")
            with self.assertRaises(DashboardContractError) as err3:
                validate_dashboard_production(project_root=root)
            self.assertIn("national_timeseries_contract", str(err3.exception))
            nat_path.write_bytes(original_nat)
            (prod_dir / OUTPUT_HASH_MANIFEST_FILE).write_bytes(original_manifest)

            # 4. Ranking NaN guard check even if manifest is rehashed.
            rank_path = prod_dir / "dashboard_regional_ranking.csv"
            original_rank = rank_path.read_bytes()
            rank_df = pd.read_csv(rank_path)
            rank_df.loc[
                rank_df["region_id"].eq("YO") & rank_df["year"].eq(2020),
                "supply_rank_desc",
            ] = 34.0
            write_csv(rank_df, rank_path)
            _rehash_manifest_entry(prod_dir, "dashboard_regional_ranking.csv")
            with self.assertRaises(DashboardContractError) as err4:
                validate_dashboard_production(project_root=root)
            self.assertIn("regional_ranking_contract", str(err4.exception))
            rank_path.write_bytes(original_rank)
            (prod_dir / OUTPUT_HASH_MANIFEST_FILE).write_bytes(original_manifest)

            restored = validate_dashboard_production(project_root=root)
            self.assertTrue(restored["passed"].all())

    def test_dynamic_validation_handles_custom_region_and_period_config(self) -> None:
        with PortableProject() as root:
            # Configure a 3-region, 5-year (2018-2022) synthetic project (15 rows, 1 missing pair).
            dash_cfg = json.loads(
                (root / "configs/dashboard/production.json").read_text(encoding="utf-8")
            )
            dash_cfg["history_start_year"] = 2018
            dash_cfg["history_end_year"] = 2020
            dash_cfg["forecast_start_year"] = 2021
            dash_cfg["forecast_end_year"] = 2022
            dash_cfg["expected_regions"] = 3
            (root / "configs/dashboard/production.json").write_text(
                json.dumps(dash_cfg, indent=2) + "\n", encoding="utf-8"
            )

            fc_cfg = json.loads(
                (root / "configs/forecasting/production.json").read_text(encoding="utf-8")
            )
            fc_cfg["history_start_year"] = 2018
            fc_cfg["history_end_year"] = 2020
            fc_cfg["forecast_start_year"] = 2021
            fc_cfg["forecast_end_year"] = 2022
            fc_cfg["expected_regions"] = 3
            fc_cfg["one_step_target_years"] = [2019, 2020]
            fc_cfg["recursive_origins"] = [2019]
            fc_cfg["recursive_max_horizon"] = 1
            fc_cfg["missing_data"]["interpolate_years"] = []
            fc_cfg["supply"]["model_params"]["break_year"] = 2019
            fc_cfg["supply"]["model_params"]["national_start_year"] = 2018
            (root / "configs/forecasting/production.json").write_text(
                json.dumps(fc_cfg, indent=2) + "\n", encoding="utf-8"
            )

            regions_df = pd.read_csv(root / "data/reference/regions.csv").head(3).copy()
            regions_df["region_id"] = ["R1", "R2", "R3"]
            regions_df["modeling_order"] = [1, 2, 3]
            regions_df.to_csv(
                root / "data/reference/regions.csv",
                index=False,
                encoding="utf-8",
                lineterminator="\n",
            )

            combined_rows: list[dict[str, object]] = []
            for order, (r_id, name, base) in enumerate(
                (("R1", "Region 1", 100.0), ("R2", "Region 2", 500.0), ("R3", "Region 3", 1000.0)),
                start=1,
            ):
                for yr in range(2018, 2023):
                    is_forecast = yr >= 2021
                    missing_supply = r_id == "R1" and yr == 2018
                    dem = base + (yr - 2018) * 10.0
                    sup = float("nan") if missing_supply else base * 1.1 + (yr - 2018) * 12.0
                    avail = not missing_supply
                    combined_rows.append(
                        {
                            "region_id": r_id,
                            "region_name": name,
                            "modeling_order": order,
                            "year": yr,
                            "data_type": "forecast" if is_forecast else "historical",
                            "demand_gwh": dem,
                            "supply_gwh": sup,
                            "accounting_difference_gwh": (sup - dem) if avail else float("nan"),
                            "demand_available": True,
                            "supply_available": avail,
                            "difference_available": avail,
                            "demand_status": "forecast" if is_forecast else "observed",
                            "supply_status": (
                                "missing" if missing_supply else ("forecast" if is_forecast else "observed")
                            ),
                            "demand_interpolated": False,
                            "supply_interpolated": False,
                            "demand_model_id": "demand_production_drift",
                            "supply_model_id": "supply_production_national_reconciled_v2",
                        }
                    )
            pd.DataFrame(combined_rows).to_csv(
                root / "outputs/production/combined/regional_energy_history_forecast.csv",
                index=False,
                encoding="utf-8",
                lineterminator="\n",
            )

            prod_models = pd.DataFrame(
                [
                    {
                        "domain": "demand",
                        "production_model_id": "demand_production_drift",
                        "model_label": "Drift",
                        "protocol": "rolling_one_step",
                        "prediction_count": 6,
                        "macro_smape_percent": 4.2,
                        "macro_mase": 0.9,
                        "micro_rmse_gwh": 15.0,
                        "aggregate_bias_percent": 0.1,
                        "selected_for_production": True,
                        "selection_note": "Synthetic",
                    },
                    {
                        "domain": "demand",
                        "production_model_id": "demand_production_drift",
                        "model_label": "Drift",
                        "protocol": "recursive_multi_step",
                        "prediction_count": 3,
                        "macro_smape_percent": 5.1,
                        "macro_mase": 1.0,
                        "micro_rmse_gwh": 18.0,
                        "aggregate_bias_percent": -0.2,
                        "selected_for_production": True,
                        "selection_note": "Synthetic",
                    },
                    {
                        "domain": "supply",
                        "production_model_id": "supply_production_national_reconciled_v2",
                        "model_label": "National Reconciled Supply (Drift National -> Step Intervention Damped)",
                        "protocol": "rolling_one_step",
                        "prediction_count": 6,
                        "macro_smape_percent": 8.5,
                        "macro_mase": 1.4,
                        "micro_rmse_gwh": 25.0,
                        "aggregate_bias_percent": -0.5,
                        "selected_for_production": True,
                        "selection_note": "Synthetic",
                    },
                    {
                        "domain": "supply",
                        "production_model_id": "supply_production_national_reconciled_v2",
                        "model_label": "National Reconciled Supply (Drift National -> Step Intervention Damped)",
                        "protocol": "recursive_multi_step",
                        "prediction_count": 3,
                        "macro_smape_percent": 11.2,
                        "macro_mase": 1.8,
                        "micro_rmse_gwh": 32.0,
                        "aggregate_bias_percent": -0.8,
                        "selected_for_production": True,
                        "selection_note": "Synthetic",
                    },
                ]
            )
            prod_models.to_csv(
                root / "outputs/production/metrics/production_model_summary.csv",
                index=False,
                encoding="utf-8",
                lineterminator="\n",
            )
            pd.DataFrame([{"check_id": "synthetic", "passed": True}]).to_csv(
                root / "outputs/production/reports/production_contract_checks.csv",
                index=False,
                encoding="utf-8",
                lineterminator="\n",
            )

            result = run_dashboard_pipeline(project_root=root, run_frontend_build=False)
            release_checks = validate_frontend_release(project_root=root)

        self.assertEqual(result["staging"]["region_rows"], 15)
        self.assertEqual(result["staging"]["regions"], 3)
        self.assertEqual(result["staging"]["complete_pairs"], 14)
        self.assertEqual(result["staging"]["historical_incomplete_pairs"], 1)
        self.assertTrue(result["production_checks"]["passed"].all())
        self.assertTrue(release_checks["passed"].all())

    def test_path_portability_reports_dir_and_vercel_exclusion(self) -> None:
        with PortableProject() as root:
            # First run creates production; second run triggers backup archive.
            run_dashboard_pipeline(project_root=root, run_frontend_build=False)
            result = run_dashboard_pipeline(project_root=root, run_frontend_build=False)
            archive = result["promotion"]["archive"]
            self.assertIsNotNone(archive)
            self.assertNotIn("\\", archive)
            self.assertNotIn(":", archive)
            self.assertFalse(Path(archive).is_absolute())

            # Remove reports dir to verify validate_dashboard_production recreates it.
            reports_dir = root / "outputs/dashboard/reports"
            shutil.rmtree(reports_dir)
            checks = validate_dashboard_production(project_root=root)
            self.assertTrue(checks["passed"].all())
            self.assertTrue((reports_dir / "dashboard_production_checks.csv").is_file())

            # .vercel directory must be ignored by snapshot_frontend.
            vercel_file = root / "frontend-dashboard/.vercel/output/config.json"
            vercel_file.parent.mkdir(parents=True, exist_ok=True)
            vercel_file.write_text('{"version": 3}\n', encoding="utf-8")
            refresh_res = refresh_frontend_data(project_root=root, run_build=False)
            self.assertEqual(refresh_res["nondata_files_changed"], [])

            # full_pipeline_latest.json must store portable project_root ".".
            full_summary = run_full_pipeline(
                project_root=root,
                start_at="dashboard",
                run_frontend_production_build=False,
            )
            self.assertEqual(full_summary["project_root"], ".")

    def test_subprocess_utf8_encoding_and_unified_build_target(self) -> None:
        with PortableProject() as root:
            run_dashboard_pipeline(project_root=root, run_frontend_build=False)
            fake_completed = subprocess.CompletedProcess(
                args=["npm", "run", "build"],
                returncode=0,
                stdout="✓ built in 1.2s │ nodejs24.x\n",
            )
            with (
                mock.patch("ecadin_energy.pipeline.release.shutil.which", return_value="npm"),
                mock.patch("ecadin_energy.pipeline.release.subprocess.run", return_value=fake_completed) as mock_run,
            ):
                refresh_res = refresh_frontend_data(
                    project_root=root,
                    run_build=True,
                    build_target="vercel",
                )
            self.assertEqual(refresh_res["build"]["target"], "vercel")
            self.assertIn("✓", refresh_res["build"]["output_tail"])
            kwargs = mock_run.call_args.kwargs
            self.assertEqual(kwargs["encoding"], "utf-8")
            self.assertEqual(kwargs["errors"], "replace")
            self.assertEqual(kwargs["env"].get("VERCEL"), "1")

            with (
                mock.patch("ecadin_energy.pipeline.release.shutil.which", return_value="npm"),
                mock.patch("ecadin_energy.pipeline.release.subprocess.run", return_value=fake_completed) as mock_run_local,
            ):
                local_res = run_frontend_build(project_root=root, target="local")
            self.assertEqual(local_res["target"], "local")
            self.assertNotIn("VERCEL", mock_run_local.call_args.kwargs["env"])


if __name__ == "__main__":
    unittest.main()
