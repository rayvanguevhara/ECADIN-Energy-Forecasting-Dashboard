from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ecadin_energy.dashboard.validation import validate_dashboard_production, validate_dashboard_staging


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate ECADIN dashboard staging and production outputs.")
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()
    staging = validate_dashboard_staging(project_root=args.project_root, config_path=args.config)
    production = validate_dashboard_production(project_root=args.project_root, config_path=args.config)
    print("ECADIN DASHBOARD VALIDATION: PASSED")
    print(f"Staging contracts    : {int(staging['passed'].sum())}/{len(staging)} PASSED")
    print(f"Production contracts : {int(production['passed'].sum())}/{len(production)} PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
