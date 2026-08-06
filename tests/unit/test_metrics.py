from __future__ import annotations

import unittest

import pandas as pd

from ecadin_energy.forecasting.evaluation.metrics import (
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


if __name__ == "__main__":
    unittest.main()
