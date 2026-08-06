from __future__ import annotations

import unittest

import pandas as pd

from ecadin_energy.forecasting.models.drift import DriftModel
from ecadin_energy.forecasting.models.registry import create_model


class DriftModelTest(unittest.TestCase):
    def test_drift_formula(self) -> None:
        history = pd.DataFrame(
            {
                "year": [2011, 2014],
                "target_gwh": [100.0, 160.0],
            }
        )
        prediction = DriftModel().predict_next(history, 2016)
        self.assertAlmostEqual(prediction, 200.0)

    def test_registry(self) -> None:
        self.assertEqual(create_model("drift").model_id, "drift")
        self.assertEqual(
            create_model("supply_production_drift_v1").model_label,
            "Drift",
        )


if __name__ == "__main__":
    unittest.main()
