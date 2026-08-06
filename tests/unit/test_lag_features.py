from __future__ import annotations

import unittest

import pandas as pd

from ecadin_energy.forecasting.exceptions import ContractError
from ecadin_energy.forecasting.features.lags import build_lag_features


class LagFeaturesTest(unittest.TestCase):
    def test_lags_use_only_prior_years(self) -> None:
        history = pd.DataFrame(
            {
                "year": [2020, 2021, 2022],
                "target_gwh": [10.0, 12.0, 15.0],
            }
        )
        features = build_lag_features(
            history,
            target_year=2023,
            lags=(1, 2, 3),
            rolling_windows=(3,),
        )
        self.assertEqual(features["lag_1_gwh"], 15.0)
        self.assertEqual(features["lag_2_gwh"], 12.0)
        self.assertEqual(features["lag_3_gwh"], 10.0)
        self.assertEqual(features["rolling_mean_3_gwh"], 37.0 / 3.0)

    def test_target_year_in_history_is_leakage(self) -> None:
        history = pd.DataFrame(
            {"year": [2022, 2023], "target_gwh": [10.0, 99.0]}
        )
        with self.assertRaises(ContractError):
            build_lag_features(history, target_year=2023)


if __name__ == "__main__":
    unittest.main()
