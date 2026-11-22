from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest

import numpy as np
import pandas as pd

from ecadin_energy.forecasting.backtesting.runner import run_backtests
from ecadin_energy.forecasting.configuration import load_production_config
from ecadin_energy.forecasting.data.loaders import (
    load_regional_master,
    load_regions,
)
from ecadin_energy.forecasting.data.panels import build_supply_panel
from ecadin_energy.forecasting.exceptions import ConfigurationError
from ecadin_energy.forecasting.models.drift import DriftModel
from ecadin_energy.forecasting.models.national_reconciled import (
    NationalReconciledSupplyModel,
    StepInterventionDampedModel,
)
from ecadin_energy.forecasting.production.supply import build_supply_forecast


def _load_fixture_supply_panel() -> tuple[pd.DataFrame, object]:
    root = Path(__file__).resolve().parents[2]
    config = load_production_config(project_root=root)
    master = load_regional_master(
        project_root=root,
        path=root / "tests/fixtures/forecasting/regional_energy_master.csv",
    )
    regions = load_regions(project_root=root)
    panel = build_supply_panel(master, regions, config)
    return panel, config


class NationalReconciledSupplyTest(unittest.TestCase):
    def test_zero_leakage_future_perturbation(self) -> None:
        panel, config = _load_fixture_supply_panel()
        params = config.supply.model_params
        assert params is not None
        model = NationalReconciledSupplyModel.from_params(params)
        region_ids = tuple(panel["region_id"].drop_duplicates().astype(str).tolist())

        for origin in (2018, 2019, 2020, 2021):
            forecast_years = tuple(origin + h for h in (1, 2, 3))
            baseline_preds = model.forecast_panel(
                panel,
                origin,
                forecast_years,
                region_ids,
            )
            perturbed = panel.copy()
            future_mask = perturbed["year"].gt(origin)
            perturbed.loc[future_mask, "training_gwh"] = (
                perturbed.loc[future_mask, "training_gwh"].fillna(10.0) * 100.0
                + 99999.0
            )
            perturbed.loc[future_mask, "actual_gwh"] = (
                perturbed.loc[future_mask, "actual_gwh"].fillna(10.0) * 100.0
                + 99999.0
            )
            perturbed_preds = model.forecast_panel(
                perturbed,
                origin,
                forecast_years,
                region_ids,
            )
            max_diff = max(
                abs(baseline_preds[key] - perturbed_preds[key])
                for key in baseline_preds
            )
            self.assertEqual(max_diff, 0.0)

    def test_aggregate_conservation_matches_national_drift(self) -> None:
        panel, config = _load_fixture_supply_panel()
        params = config.supply.model_params
        assert params is not None
        model = NationalReconciledSupplyModel.from_params(params)
        region_ids = tuple(panel["region_id"].drop_duplicates().astype(str).tolist())
        drift = DriftModel()

        scenarios = (
            (2018, (2019, 2020, 2021)),
            (2020, (2021, 2022, 2023)),
            (2021, (2022, 2023, 2024)),
            (config.history_end_year, config.forecast_years),
        )
        for origin, forecast_years in scenarios:
            reconciled = model.forecast_panel(
                panel,
                origin,
                forecast_years,
                region_ids,
            )
            eligible = panel.loc[
                panel["year"].le(origin)
                & panel["year"].ge(params.national_start_year)
                & panel["training_eligible"]
                & panel["training_gwh"].notna()
            ]
            nat_hist = (
                eligible.groupby("year", as_index=False)["training_gwh"]
                .sum()
                .rename(columns={"training_gwh": "target_gwh"})
                .sort_values("year")
                .reset_index(drop=True)
            )
            hist_work = nat_hist.copy()
            for year in forecast_years:
                expected_nat = max(0.0, float(drift.predict_next(hist_work, year)))
                hist_work = pd.concat(
                    [
                        hist_work,
                        pd.DataFrame({"year": [year], "target_gwh": [expected_nat]}),
                    ],
                    ignore_index=True,
                )
                regional_sum = sum(reconciled[(rid, year)] for rid in region_ids)
                self.assertAlmostEqual(regional_sum, expected_nat, delta=1e-6)

    def test_config_driven_parameters_validation_and_nonnegativity(self) -> None:
        panel, config = _load_fixture_supply_panel()
        params = config.supply.model_params
        assert params is not None
        self.assertEqual(config.supply.model_name, "national_reconciled_supply")
        self.assertEqual(
            config.supply.production_model_id,
            "supply_production_national_reconciled_v2",
        )
        self.assertEqual(params.break_year, 2021)
        self.assertEqual(params.ridge_lambda, 25.0)
        self.assertEqual(params.damping_phi, 0.85)
        self.assertEqual(params.national_start_year, 2013)

        # Changing config hyperparameters alters reconciled regional shares cleanly.
        region_ids = tuple(panel["region_id"].drop_duplicates().astype(str).tolist())
        base_model = NationalReconciledSupplyModel.from_params(params)
        alt_model = NationalReconciledSupplyModel(
            break_year=params.break_year,
            ridge_lambda=2.0,
            damping_phi=0.60,
            national_start_year=params.national_start_year,
        )
        base_preds = base_model.forecast_panel(
            panel, config.history_end_year, config.forecast_years, region_ids
        )
        alt_preds = alt_model.forecast_panel(
            panel, config.history_end_year, config.forecast_years, region_ids
        )
        max_region_diff = max(
            abs(base_preds[k] - alt_preds[k]) for k in base_preds
        )
        self.assertGreater(max_region_diff, 1.0)

        # Sharply declining synthetic series never produces negative predictions.
        declining_panel = pd.DataFrame(
            [
                {
                    "region_id": "D1",
                    "year": y,
                    "training_gwh": max(1.0, 500.0 - 90.0 * (y - 2018)),
                    "training_eligible": True,
                }
                for y in range(2018, 2025)
            ]
            + [
                {
                    "region_id": "D2",
                    "year": y,
                    "training_gwh": 1000.0 + 100.0 * (y - 2018),
                    "training_eligible": True,
                }
                for y in range(2018, 2025)
            ]
        )
        neg_guard_preds = base_model.forecast_panel(
            declining_panel, 2024, (2025, 2026, 2027, 2028, 2029, 2030), ("D1", "D2")
        )
        self.assertTrue(all(np.isfinite(v) and v >= 0.0 for v in neg_guard_preds.values()))

        # Invalid config values raise ConfigurationError.
        root = Path(__file__).resolve().parents[2]
        raw_cfg = json.loads(
            (root / "configs/forecasting/production.json").read_text(encoding="utf-8")
        )
        with tempfile.TemporaryDirectory() as tmp:
            bad_path = Path(tmp) / "bad_production.json"
            for field, bad_val in (
                ("ridge_lambda", 0.0),
                ("damping_phi", 1.5),
                ("break_year", 2005),
                ("national_start_year", 2024),
            ):
                mutated = json.loads(json.dumps(raw_cfg))
                mutated["supply"]["model_params"][field] = bad_val
                bad_path.write_text(json.dumps(mutated), encoding="utf-8")
                with self.assertRaises(ConfigurationError):
                    load_production_config(bad_path, project_root=root)

            mutated_missing = json.loads(json.dumps(raw_cfg))
            del mutated_missing["supply"]["model_params"]
            bad_path.write_text(json.dumps(mutated_missing), encoding="utf-8")
            with self.assertRaises(ConfigurationError):
                load_production_config(bad_path, project_root=root)

        with self.assertRaises(ValueError):
            StepInterventionDampedModel(
                break_year=2021, ridge_lambda=-1.0, damping_phi=0.85
            )
        with self.assertRaises(ValueError):
            StepInterventionDampedModel(
                break_year=2021, ridge_lambda=25.0, damping_phi=0.0
            )

    def test_k3_recalibration_sanity_and_national_q95_suppression(self) -> None:
        panel, config = _load_fixture_supply_panel()
        backtests = run_backtests(panel, config, domain="supply")
        self.assertEqual(
            sorted(backtests["predictions"]["model"].unique()),
            sorted(
                [
                    "average_growth_3",
                    "drift",
                    "moving_average_3",
                    "naive_lag1",
                    "national_reconciled_supply",
                ]
            ),
        )
        forecast, calibration, _ = build_supply_forecast(
            panel, backtests["predictions"], config
        )

        # Calibration source uses national_reconciled_supply recursive residuals.
        self.assertTrue(
            calibration.loc[
                calibration["calibration_scope"].eq("regional")
                & calibration["horizon"].le(3),
                "calibration_source",
            ]
            .str.contains("national_reconciled_supply")
            .all()
        )
        # Small bucket stays bounded without small-denominator blowup.
        small_h6 = calibration.loc[
            calibration["calibration_scope"].eq("regional")
            & calibration["size_bucket"].eq("small")
            & calibration["horizon"].eq(6)
        ].iloc[0]
        self.assertLess(float(small_h6["q95_absolute_scaled_error"]), 5.0)
        small_2030 = forecast.loc[
            forecast["year"].eq(2030)
            & forecast["uncertainty_size_bucket"].eq("small")
            & forecast["forecast_gwh"].gt(100.0)
        ]
        self.assertFalse(small_2030.empty)
        self.assertTrue(
            (
                small_2030["forecast_upper_95_gwh"] / small_2030["forecast_gwh"]
                < 10.0
            ).all()
        )

        # National q95 stays suppressed when n < 10.
        national = calibration.loc[calibration["calibration_scope"].eq("national")]
        self.assertEqual(len(national), 6)
        self.assertTrue(national["q95_status"].eq("insufficient_sample_size").all())
        self.assertTrue(national["q95_absolute_scaled_error"].isna().all())
        self.assertTrue(national["q95_lower_log_error"].isna().all())
        self.assertTrue(national["q95_upper_log_error"].isna().all())


if __name__ == "__main__":
    unittest.main()
