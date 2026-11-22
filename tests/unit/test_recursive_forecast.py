from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from ecadin_energy.forecasting.models.baselines import MovingAverage3Model
from ecadin_energy.forecasting.models.drift import DriftModel
from ecadin_energy.forecasting.strategies.recursive import (
    recursive_forecast_without_actuals,
    run_recursive_for_model,
)


class RecursiveForecastTest(unittest.TestCase):
    def test_recursive_history_uses_predictions(self) -> None:
        history = pd.DataFrame(
            {
                "year": [2018, 2019],
                "target_gwh": [100.0, 120.0],
            }
        )
        forecast = recursive_forecast_without_actuals(
            history,
            model=DriftModel(),
            forecast_years=(2020, 2021, 2022),
        )
        self.assertEqual(forecast["prediction_gwh"].tolist(), [140.0, 160.0, 180.0])
        self.assertEqual(forecast["horizon"].tolist(), [1, 2, 3])

    def test_recursive_backtest_appends_prediction_when_target_missing(self) -> None:
        region_frame = pd.DataFrame(
            {
                "region_id": ["XX"] * 6,
                "region_name": ["TEST REGION"] * 6,
                "year": [2017, 2018, 2019, 2020, 2021, 2022],
                "training_gwh": [100.0, 200.0, 300.0, 400.0, np.nan, 500.0],
                "actual_gwh": [100.0, 200.0, 300.0, 400.0, np.nan, 500.0],
                "training_eligible": [True, True, True, True, False, True],
                "validation_eligible": [True, True, True, True, False, True],
            }
        )
        rows = run_recursive_for_model(
            region_frame,
            model=MovingAverage3Model(),
            domain="supply",
            model_version="test_v1",
            reference_baseline="drift",
            origins=(2019,),
            max_horizon=3,
        )
        # 2021 is missing so only 2020 (h=1) and 2022 (h=3) are recorded for evaluation,
        # but h=2 (2021) prediction 233.333... must still be appended before predicting h=3 (2022).
        self.assertEqual([r["forecast_year"] for r in rows], [2020, 2022])
        self.assertEqual([r["horizon"] for r in rows], [1, 3])
        self.assertAlmostEqual(float(rows[0]["prediction_gwh"]), 200.0)
        expected_h2 = (200.0 + 300.0 + 200.0) / 3.0
        expected_h3 = (300.0 + 200.0 + expected_h2) / 3.0
        self.assertAlmostEqual(float(rows[1]["prediction_gwh"]), expected_h3)


if __name__ == "__main__":
    unittest.main()
