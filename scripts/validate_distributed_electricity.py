from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ecadin_energy.data_processing.cleaning.distributed_electricity import (
    validate_distributed_electricity,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate distributed electricity outputs.")
    parser.add_argument("--project-root", type=Path, default=None)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = validate_distributed_electricity(project_root=args.project_root)
    print("ECADIN DISTRIBUTED ELECTRICITY VALIDATION: PASSED")
    print(f"Canonical rows : {result['canonical_rows']}")
    print(f"Regions        : {result['regions']}")
    print(f"Years          : {result['years']}")
    print(f"Rows with value: {result['rows_with_value']}")
    print(f"Missing rows   : {result['missing_rows']}")
    print(f"Lineage rows   : {result['lineage_rows']}")
    print(f"Quality flags  : {result['quality_flags']}")
    print(f"YoY warnings   : {result['large_yoy_warning_flags']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
