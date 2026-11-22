from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ecadin_energy.data_processing.cleaning.electricity_customers import (
    validate_electricity_customers,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate electricity customers outputs.")
    parser.add_argument("--project-root", type=Path, default=None)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = validate_electricity_customers(project_root=args.project_root)
    print("ECADIN ELECTRICITY CUSTOMERS VALIDATION: PASSED")
    print(f"Geographic scope       : {result['geographic_scope']}")
    print(f"Detail rows            : {result['detail_rows']}")
    print(f"Detail rows with value : {result['detail_rows_with_value']}")
    print(f"Detail missing rows    : {result['detail_missing_rows']}")
    print(f"Total rows             : {result['total_rows']}")
    print(f"Total rows with value  : {result['total_rows_with_value']}")
    print(f"Customer groups        : {result['customer_groups']}")
    print(f"Lineage rows           : {result['lineage_rows']}")
    print(f"Quality flags          : {result['quality_flags']}")
    print(f"National total alerts  : {result['national_total_mismatch_flags']}")
    print(f"YoY warnings           : {result['large_yoy_warning_flags']}")
    print("Regional master        : NOT ELIGIBLE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
