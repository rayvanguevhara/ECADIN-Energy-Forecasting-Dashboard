from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ecadin_energy.data_processing.mastering.canonical_masters import (
    build_canonical_masters,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build canonical master tables.")
    parser.add_argument("--project-root", type=Path, default=None)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    summary = build_canonical_masters(project_root=args.project_root)
    regional = summary["regional_master"]
    national = summary["national_customer_group_master"]

    print("ECADIN CANONICAL MASTERS BUILD: COMPLETED")
    print(f"Regional rows          : {regional['rows']}")
    print(f"Regional complete      : {regional['complete_rows']}")
    print(f"Regional incomplete    : {regional['incomplete_rows']}")
    print(f"Regional coverage      : {regional['year_coverage']}")
    print(f"National rows          : {national['rows']}")
    print(f"National complete      : {national['complete_rows']}")
    print(f"National incomplete    : {national['incomplete_rows']}")
    print(f"National coverage      : {national['year_coverage']}")
    print("Imputation             : NO")
    print("Source quality flags   : UNCHANGED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
