from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ecadin_energy.data_processing.cleaning.electricity_customers import (
    build_electricity_customers,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build canonical electricity customers data.")
    parser.add_argument("--project-root", type=Path, default=None)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    summary = build_electricity_customers(project_root=args.project_root)
    print("ECADIN ELECTRICITY CUSTOMERS BUILD: COMPLETED")
    print(f"Geographic scope       : {summary['geographic_scope']}")
    print(f"Source files           : {summary['source_files']}")
    print(f"Source coverage        : {summary['source_coverage']}")
    print(f"Missing source year    : {summary['missing_source_years']}")
    print(f"Customer groups        : {summary['customer_groups']}")
    print(f"Detail rows            : {summary['detail_rows']}")
    print(f"Detail rows with value : {summary['detail_rows_with_value']}")
    print(f"Detail missing rows    : {summary['detail_missing_rows']}")
    print(f"Total rows             : {summary['total_rows']}")
    print(f"Quality flags          : {summary['quality_flags']}")
    print(f"YoY review flags       : {summary['large_yoy_warning_flags']}")
    print("Regional master        : NOT ELIGIBLE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
