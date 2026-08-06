from __future__ import annotations

import unittest
from decimal import Decimal

from ecadin_energy.data_processing.audit.statistik_listrik_bps import (
    _classify_regional_comparison,
    _parse_decimal,
)


class StatistikListrikBpsAuditTest(unittest.TestCase):
    def test_parse_indonesian_decimal(self) -> None:
        self.assertEqual(_parse_decimal("1.234,56"), Decimal("1234.56"))
        self.assertEqual(_parse_decimal("0,00"), Decimal("0.00"))

    def test_dash_is_zero_and_ellipsis_is_missing(self) -> None:
        self.assertEqual(_parse_decimal("–"), Decimal("0"))
        self.assertIsNone(_parse_decimal("..."))

    def test_exact_comparison_uses_two_decimal_tolerance(self) -> None:
        self.assertEqual(
            _classify_regional_comparison(
                Decimal("100.00"),
                Decimal("100.00"),
            ),
            "exact_match",
        )

    def test_revision_candidate(self) -> None:
        self.assertEqual(
            _classify_regional_comparison(
                Decimal("101.00"),
                Decimal("100.00"),
            ),
            "revision_candidate",
        )

    def test_missing_vs_zero_is_reviewed(self) -> None:
        self.assertEqual(
            _classify_regional_comparison(Decimal("0"), None),
            "canonical_missing_pdf_zero",
        )


if __name__ == "__main__":
    unittest.main()
