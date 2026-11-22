from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ecadin_energy.data_processing.mastering.canonical_masters import (
    validate_canonical_masters,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate canonical master tables.")
    parser.add_argument("--project-root", type=Path, default=None)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = validate_canonical_masters(project_root=args.project_root)

    print("ECADIN CANONICAL MASTERS VALIDATION: PASSED")
    print(f"Regional rows          : {result['regional_rows']}")
    print(f"Regional complete      : {result['regional_complete_rows']}")
    print(f"Regional incomplete    : {result['regional_incomplete_rows']}")
    print(f"Regional regions       : {result['regional_regions']}")
    print(f"Regional years         : {result['regional_years']}")
    print(f"National rows          : {result['national_rows']}")
    print(f"National complete      : {result['national_complete_rows']}")
    print(f"National incomplete    : {result['national_incomplete_rows']}")
    print(f"Customer groups        : {result['national_customer_groups']}")
    print(f"National years         : {result['national_years']}")
    print(f"Completeness rows      : {result['completeness_rows']}")
    print(f"Input hash rows        : {result['input_hash_rows']}")
    print("Imputation             : NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
