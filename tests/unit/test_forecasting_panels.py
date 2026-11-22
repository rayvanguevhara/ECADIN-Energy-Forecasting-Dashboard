from __future__ import annotations

from dataclasses import replace
import unittest
from pathlib import Path

from ecadin_energy.forecasting.configuration import (
    load_production_config,
    validate_production_config,
)
from ecadin_energy.forecasting.data.loaders import (
    load_regional_master,
    load_regions,
)
from ecadin_energy.forecasting.data.panels import (
    build_demand_panel,
    build_modeling_panel,
    build_supply_panel,
)
from ecadin_energy.forecasting.exceptions import (
    ConfigurationError,
    ContractError,
)


class ForecastingPanelsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        root = Path(__file__).resolve().parents[2]
        cls.config = load_production_config(project_root=root)
        master = load_regional_master(
            project_root=root,
            path=root
            / "tests/fixtures/forecasting/regional_energy_master.csv",
        )
        regions = load_regions(project_root=root)
        cls.demand = build_demand_panel(master, regions, cls.config)
        cls.supply = build_supply_panel(master, regions, cls.config)

    def test_panel_key_contract(self) -> None:
        self.assertEqual(len(self.demand), 476)
        self.assertEqual(len(self.supply), 476)
        self.assertEqual(self.demand["region_id"].nunique(), 34)
        self.assertFalse(
            self.demand.duplicated(["region_id", "year"]).any()
        )

    def test_only_2016_is_interpolated(self) -> None:
        self.assertEqual(
            set(
                self.demand.loc[
                    self.demand["is_interpolated_target"],
                    "year",
                ]
            ),
            {2016},
        )
        self.assertEqual(
            int(self.demand["is_interpolated_target"].sum()),
            34,
        )
        self.assertEqual(
            int(self.supply["is_interpolated_target"].sum()),
            34,
        )

    def test_kalimantan_boundary_exclusion(self) -> None:
        rows = self.demand.loc[
            self.demand["region_id"].isin(["KI", "KU"])
            & self.demand["year"].lt(2013)
        ]
        self.assertTrue(rows["training_gwh"].isna().all())
        self.assertFalse(rows["validation_eligible"].any())

    def test_non_2016_missing_is_not_silently_filled(self) -> None:
        yo_2020 = self.supply.loc[
            self.supply["region_id"].eq("YO")
            & self.supply["year"].eq(2020)
        ].iloc[0]
        self.assertTrue(yo_2020["training_gwh"] != yo_2020["training_gwh"])
        self.assertEqual(yo_2020["target_status"], "unavailable")

    def test_interpolation_origin_guard_rejects_leakage_config(self) -> None:
        bad_recursive = replace(
            self.config,
            recursive_origins=(2017, 2018, 2019, 2020),
        )
        with self.assertRaises(ConfigurationError):
            validate_production_config(bad_recursive)

        bad_one_step = replace(
            self.config,
            one_step_target_years=(2018, 2019, 2020),
        )
        with self.assertRaises(ConfigurationError):
            validate_production_config(bad_one_step)

    def test_build_modeling_panel_enforces_min_backtest_origin(self) -> None:
        root = Path(__file__).resolve().parents[2]
        master = load_regional_master(
            project_root=root,
            path=root
            / "tests/fixtures/forecasting/regional_energy_master.csv",
        )
        regions = load_regions(project_root=root)
        with self.assertRaises(ContractError):
            build_modeling_panel(
                master,
                regions,
                domain="demand",
                dataset_id=self.config.demand.dataset_id,
                target_column=self.config.demand.target_column,
                policy=self.config.missing_data,
                history_start_year=self.config.history_start_year,
                history_end_year=self.config.history_end_year,
                min_backtest_origin=2017,
            )
        safe_panel = build_modeling_panel(
            master,
            regions,
            domain="demand",
            dataset_id=self.config.demand.dataset_id,
            target_column=self.config.demand.target_column,
            policy=self.config.missing_data,
            history_start_year=self.config.history_start_year,
            history_end_year=self.config.history_end_year,
            min_backtest_origin=2018,
        )
        self.assertEqual(len(safe_panel), 476)


if __name__ == "__main__":
    unittest.main()
