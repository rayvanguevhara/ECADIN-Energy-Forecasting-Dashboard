from __future__ import annotations

import json
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

from ecadin_energy.forecasting.backtesting.runner import run_backtests
from ecadin_energy.forecasting.configuration import (
    DomainConfig,
    MissingDataPolicy,
    ProductionConfig,
    load_production_config,
)
from ecadin_energy.forecasting.exceptions import ContractError
from ecadin_energy.forecasting.production.accounting import (
    build_accounting_difference,
    build_combined_history_forecast,
)
from ecadin_energy.forecasting.production.demand import build_demand_forecast
from ecadin_energy.forecasting.production.supply import build_supply_forecast
from ecadin_energy.forecasting.production.validation import (
    REQUIRED_WIN_RATE_OUTPUT_KEYS,
    validate_production_frames,
    validate_written_outputs,
)
from ecadin_energy.pipeline.production import run_production_pipeline
from tests.helpers.project_fixture import PortableProject


def _make_synthetic_panel(
    *,
    domain: str,
    years: tuple[int, ...],
    missing_years: set[tuple[str, int]],
) -> pd.DataFrame:
    specs = (
        ("R1", "Region Small", 1, 200.0, 20.0),
        ("R2", "Region Medium", 2, 2000.0, 120.0),
        ("R3", "Region Large", 3, 20000.0, 500.0),
    )
    rows: list[dict[str, object]] = []
    for region_id, region_name, order, base, step in specs:
        for idx, year in enumerate(years):
            is_missing = (region_id, year) in missing_years
            val = np.nan if is_missing else float(base + idx * step)
            rows.append(
                {
                    "region_id": region_id,
                    "region_name": region_name,
                    "modeling_order": order,
                    "year": year,
                    "domain": domain,
                    "actual_gwh": val,
                    "training_gwh": val,
                    "training_eligible": not is_missing,
                    "validation_eligible": not is_missing,
                    "target_status": "missing" if is_missing else "observed",
                    "is_interpolated_target": False,
                }
            )
    return pd.DataFrame(rows)


class ProductionValidationTest(unittest.TestCase):
    def test_dynamic_validation_handles_modified_config_and_missing_counts(
        self,
    ) -> None:
        config = ProductionConfig(
            schema_version="1.0",
            history_start_year=2013,
            history_end_year=2023,
            forecast_start_year=2024,
            forecast_end_year=2025,
            expected_regions=3,
            baseline_models=("naive_lag1", "drift"),
            reference_baseline="drift",
            one_step_target_years=(2022, 2023),
            recursive_origins=(2018, 2019, 2020),
            recursive_max_horizon=3,
            missing_data=MissingDataPolicy(
                interpolate_years=(),
                exclude_pre_year_regions=(),
                exclude_before_year=2013,
                allow_silent_fill=False,
            ),
            demand=DomainConfig(
                target_column="distributed_electricity_gwh",
                dataset_id="demand_distributed_electricity",
                production_model_id="demand_production_drift",
                model_label="Drift",
                output_value_column="forecast_gwh",
            ),
            supply=DomainConfig(
                target_column="local_generation_gwh",
                dataset_id="supply_local_generation",
                production_model_id="supply_production_drift_v1",
                model_label="Drift",
                output_value_column="forecast_gwh",
            ),
            accounting_difference_label="local_generation_minus_distributed_electricity",
            accounting_disclaimer="Synthetic accounting disclaimer.",
        )

        years = config.historical_years
        demand_panel = _make_synthetic_panel(
            domain="demand",
            years=years,
            missing_years={("R1", 2014)},
        )
        supply_panel = _make_synthetic_panel(
            domain="supply",
            years=years,
            missing_years={("R1", 2015), ("R1", 2022)},
        )

        demand_bt = run_backtests(demand_panel, config, domain="demand")
        supply_bt = run_backtests(supply_panel, config, domain="supply")
        demand_fc, _ = build_demand_forecast(demand_panel, config)
        supply_fc, _, _ = build_supply_forecast(
            supply_panel,
            supply_bt["predictions"],
            config,
        )
        accounting = build_accounting_difference(demand_fc, supply_fc, config)
        combined = build_combined_history_forecast(
            demand_panel,
            supply_panel,
            accounting,
            config,
        )

        checks = validate_production_frames(
            demand_panel=demand_panel,
            supply_panel=supply_panel,
            demand_backtest=demand_bt["predictions"],
            supply_backtest=supply_bt["predictions"],
            demand_forecast=demand_fc,
            supply_forecast=supply_fc,
            accounting=accounting,
            combined=combined,
            config=config,
        )
        self.assertEqual(len(checks), 6)
        self.assertTrue(checks["passed"].all())
        demand_check = checks.loc[
            checks["check_id"].eq("demand_backtest_contract")
        ].iloc[0]
        supply_check = checks.loc[
            checks["check_id"].eq("supply_backtest_contract")
        ].iloc[0]
        combined_check = checks.loc[
            checks["check_id"].eq("combined_history_forecast")
        ].iloc[0]
        self.assertEqual(demand_check["expected"], "66")
        self.assertEqual(supply_check["expected"], "60")
        self.assertIn("historical_missing=3", str(combined_check["expected"]))

        with self.assertRaises(ContractError):
            validate_production_frames(
                demand_panel=demand_panel,
                supply_panel=supply_panel,
                demand_backtest=demand_bt["predictions"].iloc[:-1],
                supply_backtest=supply_bt["predictions"],
                demand_forecast=demand_fc,
                supply_forecast=supply_fc,
                accounting=accounting,
                combined=combined,
                config=config,
            )

    def test_written_outputs_relative_paths_and_sha256_tamper_detection(
        self,
    ) -> None:
        with PortableProject(seed_production=False) as root:
            run_production_pipeline(project_root=root)
            config = load_production_config(project_root=root)
            checks = validate_written_outputs(project_root=root, config=config)
            self.assertEqual(len(checks), 8)
            self.assertTrue(checks["passed"].all())

            summary_path = (
                root / "outputs/production/reports/production_run_summary.json"
            )
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary["project_root"], ".")
            for key, rel_path in summary["output_files"].items():
                self.assertNotIn("\\", rel_path, key)
                self.assertNotIn(":", rel_path, key)
                self.assertFalse(Path(rel_path).is_absolute(), key)
            for key in REQUIRED_WIN_RATE_OUTPUT_KEYS:
                self.assertIn(key, summary["output_files"])
                self.assertIn(key, summary["deterministic_output_hashes"])

            demand_fc = pd.read_csv(root / summary["output_files"]["demand_forecast"])
            supply_fc = pd.read_csv(root / summary["output_files"]["supply_forecast"])
            self.assertEqual(
                list(
                    zip(
                        supply_fc["modeling_order"],
                        supply_fc["region_id"],
                        supply_fc["year"],
                    )
                ),
                list(
                    zip(
                        demand_fc["modeling_order"],
                        demand_fc["region_id"],
                        demand_fc["year"],
                    )
                ),
            )
            self.assertTrue(
                demand_fc["model_version"]
                .eq("demand_production_drift")
                .all()
            )
            self.assertTrue(
                supply_fc["model_version"]
                .eq("supply_production_drift_v1")
                .all()
            )

            model_summary = pd.read_csv(
                root / summary["output_files"]["model_summary"]
            )
            self.assertEqual(
                set(model_summary["production_model_id"]),
                {"demand_production_drift", "supply_production_drift_v1"},
            )
            self.assertEqual(
                set(model_summary["model_label"]),
                {config.demand.model_label, config.supply.model_label},
            )

            tamper_output = (
                root / summary["output_files"]["demand_win_rate_by_regime"]
            )
            original_output = tamper_output.read_bytes()
            tamper_output.write_bytes(original_output + b"\n")
            with self.assertRaises(ContractError) as output_err:
                validate_written_outputs(project_root=root, config=config)
            self.assertIn(
                "demand_win_rate_by_regime",
                str(output_err.exception),
            )
            tamper_output.write_bytes(original_output)

            checks_restored = validate_written_outputs(
                project_root=root,
                config=config,
            )
            self.assertTrue(checks_restored["passed"].all())

            tamper_input = root / "data/reference/regions.csv"
            original_input = tamper_input.read_bytes()
            tamper_input.write_bytes(original_input + b" ")
            with self.assertRaises(ContractError) as input_err:
                validate_written_outputs(project_root=root, config=config)
            self.assertIn("regions", str(input_err.exception))


if __name__ == "__main__":
    unittest.main()
