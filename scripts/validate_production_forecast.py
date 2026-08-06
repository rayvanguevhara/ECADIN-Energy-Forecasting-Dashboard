from __future__ import annotations

import argparse
from pathlib import Path

from ecadin_energy.pipeline.validation import (
    validate_production_pipeline,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate written ECADIN production forecasting outputs."
    )
    parser.add_argument("--project-root", type=Path, default=None)
    parser.add_argument("--config", type=Path, default=None)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    checks = validate_production_pipeline(
        project_root=args.project_root,
        config_path=args.config,
    )
    print("ECADIN PRODUCTION FORECASTING VALIDATION: PASSED")
    print(checks.to_string(index=False))
    print(f"Contracts: {int(checks['passed'].sum())}/{len(checks)} PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
