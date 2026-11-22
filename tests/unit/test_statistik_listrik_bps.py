from __future__ import annotations

import csv
import hashlib
import shutil
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from ecadin_energy.data_processing.audit.statistik_listrik_bps import (
    _classify_regional_comparison,
    _parse_decimal,
    validate_statistik_listrik_bps,
)

SOURCE_ROOT = Path(__file__).resolve().parents[2]


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

    def test_validate_statistik_listrik_bps_detects_pdf_sha256_tampering(self) -> None:
        rel_reports = (
            "outputs/reports/data/statistik_listrik_pdf_inventory.csv",
            "outputs/reports/data/statistik_listrik_table_inventory.csv",
            "outputs/reports/data/statistik_listrik_reconciliation.csv",
            "outputs/reports/data/statistik_listrik_national_totals.csv",
            "outputs/reports/data/statistik_listrik_revision_summary.csv",
            "outputs/reports/data/statistik_listrik_bps_build_summary.json",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in rel_reports:
                dst = root / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(SOURCE_ROOT / rel, dst)

            pdf_dir = root / "data/raw/bps/statistik_listrik"
            pdf_dir.mkdir(parents=True, exist_ok=True)
            inv_path = root / "outputs/reports/data/statistik_listrik_pdf_inventory.csv"
            with inv_path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                fields = reader.fieldnames
                inv_rows = list(reader)

            for idx, row in enumerate(inv_rows):
                payload = f"%PDF-1.4\n%%ECADIN-{idx:02d}\n".encode("ascii")
                pdf_path = pdf_dir / row["filename"]
                pdf_path.write_bytes(payload)
                row["size_bytes"] = str(len(payload))
                row["sha256"] = hashlib.sha256(payload).hexdigest().upper()

            with inv_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\r\n")
                writer.writeheader()
                writer.writerows(inv_rows)

            result = validate_statistik_listrik_bps(project_root=root)
            self.assertEqual(result["pdf_hashes_verified"], 16)

            tampered_pdf = pdf_dir / inv_rows[0]["filename"]
            tampered_bytes = tampered_pdf.read_bytes()
            tampered_pdf.write_bytes(b"X" + tampered_bytes[1:])
            with self.assertRaisesRegex(ValueError, "PDF SHA-256 mismatch"):
                validate_statistik_listrik_bps(project_root=root)


if __name__ == "__main__":
    unittest.main()
