from __future__ import annotations

import unittest
from pathlib import Path

import pandas as pd

from ecadin_energy.dashboard.configuration import load_dashboard_config
from ecadin_energy.dashboard.region_detail import (
    ATTENTION_REASON_MAP,
    VALID_GAP_CATEGORIES,
    build_region_detail,
    classify_accounting_difference,
)
from ecadin_energy.dashboard.regional_ranking import build_regional_ranking


class DashboardRegionDetailTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[2]
        cls.config = load_dashboard_config(project_root=cls.root)

    def test_category_boundaries(self) -> None:
        self.assertEqual(
            classify_accounting_difference(20.0, self.config),
            "jauh_di_atas_demand",
        )
        self.assertEqual(
            classify_accounting_difference(5.0, self.config),
            "di_atas_demand",
        )
        self.assertEqual(
            classify_accounting_difference(0.0, self.config),
            "relatif_seimbang",
        )
        self.assertEqual(
            classify_accounting_difference(-5.0, self.config),
            "di_bawah_demand",
        )
        self.assertEqual(
            classify_accounting_difference(-20.0, self.config),
            "jauh_di_bawah_demand",
        )
        self.assertEqual(
            classify_accounting_difference(None, self.config),
            "tidak_tersedia",
        )

    def test_detail_contract_and_neutral_reasons(self) -> None:
        combined = pd.read_csv(
            self.root
            / "tests/fixtures/production/combined/"
            "regional_energy_history_forecast.csv"
        )
        regions = pd.read_csv(self.root / "data/reference/regions.csv")
        detail = build_region_detail(combined, regions, self.config)
        self.assertEqual(len(detail), 680)
        self.assertEqual(detail["region_id"].nunique(), 34)
        self.assertEqual(int(detail["available"].sum()), 671)
        self.assertEqual(int((detail["quality"] == "interpolated").sum()), 34)
        self.assertTrue(detail["population_jiwa"].isna().all())

        self.assertTrue(
            set(detail["gap_category"].astype(str)).issubset(set(VALID_GAP_CATEGORIES))
        )
        reasons = set(detail["attention_reason"].dropna().astype(str))
        self.assertEqual(reasons, set(ATTENTION_REASON_MAP.values()))
        for cat in detail["gap_category"].astype(str):
            self.assertNotIn("surplus", cat)
            self.assertNotIn("defisit", cat)

    def test_regional_ranking_nan_guard(self) -> None:
        combined = pd.read_csv(
            self.root
            / "tests/fixtures/production/combined/"
            "regional_energy_history_forecast.csv"
        )
        regions = pd.read_csv(self.root / "data/reference/regions.csv")
        detail = build_region_detail(combined, regions, self.config)
        ranking = build_regional_ranking(detail)

        # KI & KU 2011-2012 have both demand and supply missing -> all 3 ranks must be NA.
        ki_ku_early = ranking.loc[
            ranking["region_id"].isin({"KI", "KU"}) & ranking["year"].isin({2011, 2012})
        ]
        self.assertEqual(len(ki_ku_early), 4)
        self.assertTrue(ki_ku_early["demand_rank_desc"].isna().all())
        self.assertTrue(ki_ku_early["supply_rank_desc"].isna().all())
        self.assertTrue(ki_ku_early["difference_rank_desc"].isna().all())

        # YO 2011-2014 & 2020 has observed demand, missing supply -> demand ranked, supply/diff NA.
        yo_missing_supply = ranking.loc[
            ranking["region_id"].eq("YO") & ranking["year"].isin({2011, 2012, 2013, 2014, 2020})
        ]
        self.assertEqual(len(yo_missing_supply), 5)
        self.assertTrue(yo_missing_supply["demand_rank_desc"].notna().all())
        self.assertTrue(yo_missing_supply["supply_rank_desc"].isna().all())
        self.assertTrue(yo_missing_supply["difference_rank_desc"].isna().all())

        # All 671 complete rows must have valid numeric ranks >= 1.
        complete_rows = ranking.loc[ranking["available"]]
        self.assertEqual(len(complete_rows), 671)
        self.assertTrue((complete_rows["demand_rank_desc"] >= 1).all())
        self.assertTrue((complete_rows["supply_rank_desc"] >= 1).all())
        self.assertTrue((complete_rows["difference_rank_desc"] >= 1).all())


if __name__ == "__main__":
    unittest.main()
