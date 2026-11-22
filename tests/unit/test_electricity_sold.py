from __future__ import annotations

import csv
import shutil
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from ecadin_energy.data_processing.cleaning.annual_category_series import (
    read_annual_category_file,
)
from ecadin_energy.data_processing.cleaning.electricity_sold import (
    _classify_total_difference,
    validate_electricity_sold,
)

SOURCE_ROOT = Path(__file__).resolve().parents[2]


class ElectricitySoldCleanerTest(unittest.TestCase):
    def test_total_difference_classification(self) -> None:
        self.assertEqual(_classify_total_difference(Decimal("0")), "valid")
        self.assertEqual(
            _classify_total_difference(Decimal("0.01")),
            "valid_with_rounding_difference",
        )
        self.assertEqual(
            _classify_total_difference(Decimal("0.02")),
            "warning_source_total_mismatch",
        )

    def test_category_parser_normalizes_business_source_typo(self) -> None:
        content = (
            "Customer Group,\n"
            ",Electricity Sold (GWh)\n"
            ",2024\n"
            "Social,1\n"
            "Households,2\n"
            "Bussiness,3\n"
            "Industry,4\n"
            "Public,5\n"
            "All Customer,15\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "Electricity Sold, 2024.csv"
            path.write_text(content, encoding="utf-8")
            parsed = read_annual_category_file(
                path,
                source_label_to_category_id={
                    "Social": "social",
                    "Households": "households",
                    "Bussiness": "business",
                    "Industry": "industry",
                    "Public": "public",
                },
                total_source_label="All Customer",
            )
        self.assertEqual(parsed.values_by_category_id["business"], Decimal("3"))
        self.assertEqual(parsed.reported_total, Decimal("15"))

    def test_category_parser_rejects_unknown_label(self) -> None:
        content = (
            "Customer Group,\n"
            ",Electricity Sold (GWh)\n"
            ",2024\n"
            "Unknown,1\n"
            "All Customer,1\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "Electricity Sold, 2024.csv"
            path.write_text(content, encoding="utf-8")
            with self.assertRaises(ValueError):
                read_annual_category_file(
                    path,
                    source_label_to_category_id={"Social": "social"},
                    total_source_label="All Customer",
                )

    def test_validate_electricity_sold_detects_reconciliation_negative_and_raw_tampering(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(
                SOURCE_ROOT / "data/raw/bps/electricity_sold",
                root / "data/raw/bps/electricity_sold",
            )
            for rel in (
                "data/processed/demand/electricity_sold_by_customer_group.csv",
                "data/processed/demand/electricity_sold_total.csv",
                "data/processed/master/data_lineage.csv",
                "data/processed/master/data_quality_flags.csv",
                "outputs/reports/data/electricity_sold_build_summary.json",
            ):
                dst = root / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(SOURCE_ROOT / rel, dst)

            result = validate_electricity_sold(project_root=root)
            self.assertEqual(result["status"], "valid")

            total_path = root / "data/processed/demand/electricity_sold_total.csv"
            orig_total = total_path.read_bytes()
            with total_path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                fields = reader.fieldnames
                rows = list(reader)
            rows[0]["electricity_sold_gwh"] = "99999.00"
            with total_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\r\n")
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaisesRegex(ValueError, "customer-group sums differ"):
                validate_electricity_sold(project_root=root)

            rows[0]["electricity_sold_gwh"] = "-1.00"
            with total_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\r\n")
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaisesRegex(ValueError, "Negative electricity-sold total value"):
                validate_electricity_sold(project_root=root)

            total_path.write_bytes(orig_total)
            raw_sample = sorted((root / "data/raw/bps/electricity_sold").glob("*.csv"))[0]
            raw_sample.write_bytes(raw_sample.read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "Raw source SHA-256 mismatch"):
                validate_electricity_sold(project_root=root)


if __name__ == "__main__":
    unittest.main()
