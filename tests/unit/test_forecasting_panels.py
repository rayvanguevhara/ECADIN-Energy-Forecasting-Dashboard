from __future__ import annotations

import unittest

from ecadin_energy.forecasting.configuration import load_production_config
from ecadin_energy.forecasting.data.loaders import (
    load_regional_master,
    load_regions,
)
from ecadin_energy.forecasting.data.panels import (
    build_demand_panel,
    build_supply_panel,
)


class ForecastingPanelsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_production_config()
        master = load_regional_master()
        regions = load_regions()
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


if __name__ == "__main__":
    unittest.main()
