from __future__ import annotations

import unittest

import pandas as pd

from ecadin_energy.forecasting.models.drift import DriftModel
from ecadin_energy.forecasting.strategies.recursive import (
    recursive_forecast_without_actuals,
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


if __name__ == "__main__":
    unittest.main()
