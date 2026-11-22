from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ecadin_energy.data_processing.reference import validate_reference_layer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate ECADIN reference layer.")
    parser.add_argument("--project-root", type=Path, default=None)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = validate_reference_layer(project_root=args.project_root)
    print("ECADIN REFERENCE LAYER VALIDATION: PASSED")
    print(f"Regions       : {result['regions']}")
    print(f"Aliases       : {result['aliases']}")
    print(f"Coordinates   : {result['coordinates']}")
    print(f"Bubble-only   : {', '.join(result['bubble_only'])}")
    print(f"Canonical key : {result['canonical_key']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
