from __future__ import annotations

import math
import unittest

import pandas as pd

from ecadin_energy.forecasting.evaluation.aggregation import (
    metrics_by_region,
    metrics_summary,
)
from ecadin_energy.forecasting.evaluation.challenger import (
    win_rate_by_horizon,
    win_rate_by_regime,
    win_rate_vs_reference,
)
from ecadin_energy.forecasting.evaluation.metrics import (
    build_forecast_record,
    mase_scale,
    smape,
)


class MetricsTest(unittest.TestCase):
    def test_smape(self) -> None:
        self.assertAlmostEqual(smape(100.0, 110.0), 2000.0 / 210.0)
        self.assertEqual(smape(0.0, 0.0), 0.0)

    def test_mase_scale(self) -> None:
        history = pd.DataFrame(
            {
                "year": [2018, 2019, 2020],
                "target_gwh": [100.0, 130.0, 110.0],
            }
        )
        self.assertEqual(mase_scale(history), 25.0)

    def test_mase_scale_excludes_year_gap(self) -> None:
        gapped = pd.DataFrame(
            {
                "year": [2018, 2019, 2021, 2022],
                "target_gwh": [100.0, 110.0, 310.0, 320.0],
            }
        )
        self.assertEqual(mase_scale(gapped), 10.0)

        no_consecutive_pairs = pd.DataFrame(
            {
                "year": [2015, 2017, 2019],
                "target_gwh": [10.0, 20.0, 30.0],
            }
        )
        self.assertTrue(math.isnan(mase_scale(no_consecutive_pairs)))

    def test_mase_scale_zero_and_constant_series(self) -> None:
        zero_series = pd.DataFrame(
            {"year": [2017, 2018, 2019], "target_gwh": [0.0, 0.0, 0.0]}
        )
        constant_series = pd.DataFrame(
            {"year": [2017, 2018, 2019], "target_gwh": [42.0, 42.0, 42.0]}
        )
        yo_like_gap = pd.DataFrame(
            {
                "year": [2015, 2016, 2017, 2018, 2019, 2021],
                "target_gwh": [0.0, 0.0, 0.0, 0.0, 0.0, 3.32],
            }
        )
        self.assertTrue(math.isnan(mase_scale(zero_series)))
        self.assertTrue(math.isnan(mase_scale(constant_series)))
        self.assertTrue(math.isnan(mase_scale(yo_like_gap)))

    def test_aggregation_valid_mase_counts(self) -> None:
        const_hist = pd.DataFrame(
            {"year": [2018, 2019], "target_gwh": [0.0, 0.0]}
        )
        normal_hist = pd.DataFrame(
            {"year": [2018, 2019], "target_gwh": [100.0, 110.0]}
        )
        records = [
            build_forecast_record(
                domain="supply",
                model_version="v1",
                protocol="rolling_one_step",
                model="drift",
                reference_baseline="drift",
                region_id="YO",
                region_name="DI YOGYAKARTA",
                origin_year=2019,
                forecast_year=2020,
                horizon=1,
                history_for_scale=const_hist,
                actual=5.0,
                raw_prediction=0.0,
            ).as_dict(),
            build_forecast_record(
                domain="supply",
                model_version="v1",
                protocol="rolling_one_step",
                model="drift",
                reference_baseline="drift",
                region_id="AC",
                region_name="ACEH",
                origin_year=2019,
                forecast_year=2020,
                horizon=1,
                history_for_scale=normal_hist,
                actual=120.0,
                raw_prediction=115.0,
            ).as_dict(),
        ]
        preds = pd.DataFrame(records)
        summary = metrics_summary(preds)
        by_region = metrics_by_region(preds).set_index("region_id")
        self.assertEqual(int(summary.iloc[0]["prediction_count"]), 2)
        self.assertEqual(int(summary.iloc[0]["mase_valid_prediction_count"]), 1)
        self.assertEqual(int(summary.iloc[0]["mase_valid_region_count"]), 1)
        self.assertEqual(int(by_region.loc["YO", "mase_valid_prediction_count"]), 0)
        self.assertEqual(int(by_region.loc["AC", "mase_valid_prediction_count"]), 1)

    def test_win_rate_by_horizon_and_regime(self) -> None:
        rows = [
            # origin 2020 -> forecast 2021 (h=1, pre_2022) & 2022 (h=2, post_2021)
            ("supply", "recursive_multi_step", "AC", 2020, 2021, 1, "drift", 10.0),
            ("supply", "recursive_multi_step", "AC", 2020, 2021, 1, "naive_lag1", 5.0),
            ("supply", "recursive_multi_step", "AC", 2020, 2022, 2, "drift", 4.0),
            ("supply", "recursive_multi_step", "AC", 2020, 2022, 2, "naive_lag1", 8.0),
            # origin 2021 -> forecast 2022 (h=1, post_2021 & post_2021_origins)
            ("supply", "recursive_multi_step", "AC", 2021, 2022, 1, "drift", 3.0),
            ("supply", "recursive_multi_step", "AC", 2021, 2022, 1, "naive_lag1", 9.0),
        ]
        preds = pd.DataFrame(
            rows,
            columns=[
                "domain",
                "protocol",
                "region_id",
                "origin_year",
                "forecast_year",
                "horizon",
                "model",
                "absolute_error_gwh",
            ],
        )
        overall = win_rate_vs_reference(preds, reference_model="drift").set_index("model")
        self.assertAlmostEqual(float(overall.loc["naive_lag1", "win_rate_vs_reference"]), 1.0 / 3.0)

        by_h = win_rate_by_horizon(preds, reference_model="drift").set_index(["horizon", "model"])
        self.assertAlmostEqual(float(by_h.loc[(1, "naive_lag1"), "win_rate_vs_reference"]), 0.5)
        self.assertAlmostEqual(float(by_h.loc[(2, "naive_lag1"), "win_rate_vs_reference"]), 0.0)

        by_reg = win_rate_by_regime(preds, reference_model="drift").set_index(["regime", "model"])
        self.assertAlmostEqual(float(by_reg.loc[("pre_2022", "naive_lag1"), "win_rate_vs_reference"]), 1.0)
        self.assertAlmostEqual(float(by_reg.loc[("post_2021", "naive_lag1"), "win_rate_vs_reference"]), 0.0)
        self.assertAlmostEqual(float(by_reg.loc[("post_2021_origins", "naive_lag1"), "win_rate_vs_reference"]), 0.0)
        self.assertAlmostEqual(float(by_reg.loc[("all_years", "naive_lag1"), "win_rate_vs_reference"]), 1.0 / 3.0)


if __name__ == "__main__":
    unittest.main()
