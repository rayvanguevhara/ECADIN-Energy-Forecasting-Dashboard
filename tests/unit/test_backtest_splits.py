from __future__ import annotations

import unittest

from ecadin_energy.forecasting.backtesting.splits import (
    recursive_splits,
    rolling_one_step_splits,
)


class BacktestSplitsTest(unittest.TestCase):
    def test_rolling_contract(self) -> None:
        splits = rolling_one_step_splits((2019, 2020, 2021))
        self.assertEqual(
            [(s.origin_year, s.target_year, s.horizon) for s in splits],
            [(2018, 2019, 1), (2019, 2020, 1), (2020, 2021, 1)],
        )

    def test_recursive_contract(self) -> None:
        splits = recursive_splits((2018, 2021), 3)
        self.assertIn(
            (2018, 2021, 3),
            [(s.origin_year, s.target_year, s.horizon) for s in splits],
        )
        self.assertIn(
            (2021, 2024, 3),
            [(s.origin_year, s.target_year, s.horizon) for s in splits],
        )


if __name__ == "__main__":
    unittest.main()
