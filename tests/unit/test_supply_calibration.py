from __future__ import annotations

import math
import unittest
from pathlib import Path

import pandas as pd

from ecadin_energy.forecasting.backtesting.runner import run_backtests
from ecadin_energy.forecasting.configuration import load_production_config
from ecadin_energy.forecasting.data.loaders import (
    load_regional_master,
    load_regions,
)
from ecadin_energy.forecasting.data.panels import build_supply_panel
from ecadin_energy.forecasting.production.supply import (
    _drift_horizon_factor,
    build_supply_forecast,
    calibrate_uncertainty,
)


def _build_synthetic_panel() -> pd.DataFrame:
    regions = [
        ("SM1", "SMALL ONE", 1, [200.0 + 15.0 * i for i in range(14)]),
        ("SM2", "SMALL TWO", 2, [300.0 + 20.0 * i for i in range(14)]),
        # Migrates from small (<1000) before 2021 to medium (>=1000) in 2021
        (
            "MIG",
            "MIGRATOR",
            3,
            [40.0 + 2.0 * i if y < 2021 else 4500.0 + 100.0 * (y - 2021) for i, y in enumerate(range(2011, 2025))],
        ),
        ("MED", "MEDIUM ONE", 4, [2000.0 + 150.0 * i for i in range(14)]),
        ("LRG", "LARGE ONE", 5, [15000.0 + 800.0 * i for i in range(14)]),
    ]
    rows: list[dict[str, object]] = []
    for region_id, region_name, order, vals in regions:
        for year, val in zip(range(2011, 2025), vals):
            rows.append(
                {
                    "domain": "supply",
                    "dataset_id": "supply_local_generation",
                    "region_id": region_id,
                    "region_name": region_name,
                    "modeling_order": order,
                    "year": year,
                    "actual_gwh": val if year != 2016 else float("nan"),
                    "training_gwh": val,
                    "target_status": "interpolated" if year == 2016 else "observed",
                    "is_observed_target": year != 2016,
                    "is_interpolated_target": year == 2016,
                    "is_geography_consistent": True,
                    "training_eligible": True,
                    "validation_eligible": year != 2016,
                }
            )
    return pd.DataFrame(rows)


class SupplyCalibrationTest(unittest.TestCase):
    def test_small_bucket_excludes_2021_break_and_bucket_migration(self) -> None:
        root = Path(__file__).resolve().parents[2]
        config = load_production_config(project_root=root)
        panel = _build_synthetic_panel()
        backtests = run_backtests(panel, config, domain="supply")
        forecast, calibration, _ = build_supply_forecast(
            panel,
            backtests["predictions"],
            config,
        )
        small_h6 = calibration.loc[
            calibration["calibration_scope"].eq("regional")
            & calibration["size_bucket"].eq("small")
            & calibration["horizon"].eq(6)
        ].iloc[0]
        self.assertLess(float(small_h6["q95_absolute_scaled_error"]), 5.0)
        self.assertLess(float(small_h6["q95_upper_log_error"]), 2.0)

        ordered = (
            (forecast["forecast_lower_95_gwh"] >= 0.0)
            & (forecast["forecast_lower_95_gwh"] <= forecast["forecast_lower_80_gwh"])
            & (forecast["forecast_lower_80_gwh"] <= forecast["forecast_gwh"])
            & (forecast["forecast_gwh"] <= forecast["forecast_upper_80_gwh"])
            & (forecast["forecast_upper_80_gwh"] <= forecast["forecast_upper_95_gwh"])
        )
        self.assertTrue(ordered.all())

    def test_national_insufficient_sample_size_suppresses_q95(self) -> None:
        root = Path(__file__).resolve().parents[2]
        config = load_production_config(project_root=root)
        panel = _build_synthetic_panel()
        backtests = run_backtests(panel, config, domain="supply")
        calibration = calibrate_uncertainty(panel, backtests["predictions"])
        national = calibration.loc[
            calibration["calibration_scope"].eq("national")
        ]
        self.assertEqual(len(national), 6)
        self.assertTrue(
            national["q95_status"].eq("insufficient_sample_size").all()
        )
        self.assertTrue(national["q95_absolute_scaled_error"].isna().all())
        self.assertTrue(national["q95_lower_log_error"].isna().all())
        self.assertTrue(national["q95_upper_log_error"].isna().all())
        self.assertTrue(national["empirical_coverage_95"].isna().all())
        self.assertTrue(national["q80_absolute_scaled_error"].notna().all())
        self.assertTrue(
            national["q80_absolute_scaled_error"].is_monotonic_increasing
        )

    def test_drift_horizon_extrapolation_exceeds_sqrt_scaling(self) -> None:
        factors = [
            _drift_horizon_factor(h, anchor_horizon=3, history_span=13)
            for h in (4, 5, 6)
        ]
        self.assertEqual(factors, sorted(factors))
        for horizon, factor in zip((4, 5, 6), factors):
            self.assertGreater(factor, math.sqrt(horizon / 3.0))

    def test_fixture_supply_forecast_contract_and_reasonable_intervals(self) -> None:
        root = Path(__file__).resolve().parents[2]
        config = load_production_config(project_root=root)
        master = load_regional_master(
            project_root=root,
            path=root
            / "tests/fixtures/forecasting/regional_energy_master.csv",
        )
        regions = load_regions(project_root=root)
        panel = build_supply_panel(master, regions, config)
        backtests = run_backtests(panel, config, domain="supply")
        forecast, calibration, _ = build_supply_forecast(
            panel,
            backtests["predictions"],
            config,
        )
        self.assertEqual(len(forecast), 204)
        self.assertEqual(
            config.supply.production_model_id,
            "supply_production_national_reconciled_v2",
        )
        self.assertTrue(
            forecast["model_id"].eq(config.supply.production_model_id).all()
        )
        for column in (
            "forecast_lower_80_gwh",
            "forecast_upper_80_gwh",
            "forecast_lower_95_gwh",
            "forecast_upper_95_gwh",
        ):
            self.assertTrue(forecast[column].notna().all())

        small_2030 = forecast.loc[
            forecast["year"].eq(2030)
            & forecast["uncertainty_size_bucket"].eq("small")
            & forecast["forecast_gwh"].gt(100.0)
        ]
        ratios = small_2030["forecast_upper_95_gwh"] / small_2030["forecast_gwh"]
        self.assertTrue((ratios < 10.0).all())
        small_h6 = calibration.loc[
            calibration["calibration_scope"].eq("regional")
            & calibration["size_bucket"].eq("small")
            & calibration["horizon"].eq(6)
        ].iloc[0]
        self.assertLess(float(small_h6["q95_absolute_scaled_error"]), 5.0)


if __name__ == "__main__":
    unittest.main()
