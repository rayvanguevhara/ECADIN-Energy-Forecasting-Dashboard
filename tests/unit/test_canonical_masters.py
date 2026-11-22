from __future__ import annotations

import csv
import shutil
import tempfile
import unittest
from pathlib import Path

from ecadin_energy.data_processing.harmonization.regions import clear_reference_caches
from ecadin_energy.data_processing.mastering.canonical_masters import (
    _load_unique_index,
    _validate_numeric_text,
    validate_canonical_masters,
)

SOURCE_ROOT = Path(__file__).resolve().parents[2]


class CanonicalMastersTest(unittest.TestCase):
    def test_unique_index_accepts_blank_value(self) -> None:
        content = (
            "region_id,year,value\n"
            "AC,2016,\n"
            "AC,2017,1.25\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.csv"
            path.write_text(content, encoding="utf-8")
            index = _load_unique_index(
                path,
                key_fields=("region_id", "year"),
                required_value_fields=("value",),
            )
        self.assertEqual(index[("AC", "2016")]["value"], "")
        self.assertEqual(index[("AC", "2017")]["value"], "1.25")

    def test_unique_index_rejects_duplicate_key(self) -> None:
        content = (
            "region_id,year,value\n"
            "AC,2017,1\n"
            "AC,2017,2\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.csv"
            path.write_text(content, encoding="utf-8")
            with self.assertRaises(ValueError):
                _load_unique_index(
                    path,
                    key_fields=("region_id", "year"),
                    required_value_fields=("value",),
                )

    def test_numeric_validation_accepts_blank_and_zero(self) -> None:
        _validate_numeric_text("", context="test")
        _validate_numeric_text("0", context="test")
        _validate_numeric_text("1.25", context="test")

    def test_numeric_validation_rejects_negative(self) -> None:
        with self.assertRaises(ValueError):
            _validate_numeric_text("-1", context="test")

    def test_integer_validation_rejects_fractional_count(self) -> None:
        with self.assertRaises(ValueError):
            _validate_numeric_text(
                "1.5",
                integer_only=True,
                context="test",
            )

    def test_validate_canonical_masters_detects_direct_cell_and_completeness_tampering(
        self,
    ) -> None:
        rel_files = (
            "data/reference/regions.csv",
            "data/reference/region_aliases.csv",
            "data/reference/customer_groups.csv",
            "data/processed/demand/distributed_electricity.csv",
            "data/processed/demand/electricity_sold_by_customer_group.csv",
            "data/processed/demand/electricity_customers_by_customer_group.csv",
            "data/processed/supply/local_generation.csv",
            "data/processed/supply/installed_capacity.csv",
            "data/processed/master/regional_energy_master.csv",
            "data/processed/master/national_customer_group_master.csv",
            "outputs/reports/data/canonical_master_completeness.csv",
            "outputs/reports/data/canonical_master_input_hashes.csv",
            "outputs/reports/data/canonical_master_build_summary.json",
        )
        clear_reference_caches()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                for rel in rel_files:
                    dst = root / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(SOURCE_ROOT / rel, dst)

                result = validate_canonical_masters(project_root=root)
                self.assertEqual(result["regional_rows"], 476)

                reg_path = root / "data/processed/master/regional_energy_master.csv"
                orig_reg = reg_path.read_bytes()
                with reg_path.open("r", encoding="utf-8-sig", newline="") as handle:
                    reader = csv.DictReader(handle)
                    fields = reader.fieldnames
                    rows = list(reader)
                rows[0]["distributed_electricity_gwh"] = "999999.00"
                with reg_path.open("w", encoding="utf-8-sig", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\r\n")
                    writer.writeheader()
                    writer.writerows(rows)
                with self.assertRaisesRegex(ValueError, "Regional master cell values differ"):
                    validate_canonical_masters(project_root=root)

                reg_path.write_bytes(orig_reg)
                nat_path = root / "data/processed/master/national_customer_group_master.csv"
                orig_nat = nat_path.read_bytes()
                with nat_path.open("r", encoding="utf-8-sig", newline="") as handle:
                    reader = csv.DictReader(handle)
                    fields = reader.fieldnames
                    rows = list(reader)
                rows[0]["electricity_sold_gwh"] = "999999.00"
                with nat_path.open("w", encoding="utf-8-sig", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\r\n")
                    writer.writeheader()
                    writer.writerows(rows)
                with self.assertRaisesRegex(ValueError, "National master cell values differ"):
                    validate_canonical_masters(project_root=root)

                nat_path.write_bytes(orig_nat)
                comp_path = root / "outputs/reports/data/canonical_master_completeness.csv"
                with comp_path.open("r", encoding="utf-8-sig", newline="") as handle:
                    reader = csv.DictReader(handle)
                    fields = reader.fieldnames
                    rows = list(reader)
                rows[0]["complete_rows"] = "0"
                with comp_path.open("w", encoding="utf-8-sig", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\r\n")
                    writer.writeheader()
                    writer.writerows(rows)
                with self.assertRaisesRegex(ValueError, "Completeness table contents do not match"):
                    validate_canonical_masters(project_root=root)
        finally:
            clear_reference_caches()


if __name__ == "__main__":
    unittest.main()
