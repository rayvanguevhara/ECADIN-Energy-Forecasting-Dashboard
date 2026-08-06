from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ecadin_energy.dashboard.staging import build_dashboard_staging
from ecadin_energy.dashboard.validation import validate_dashboard_staging
from ecadin_energy.dashboard.promotion import promote_dashboard_staging


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and promote ECADIN dashboard staging outputs.")
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()
    result = build_dashboard_staging(project_root=args.project_root, config_path=args.config)
    checks = validate_dashboard_staging(project_root=args.project_root, config_path=args.config)
    promotion = promote_dashboard_staging(project_root=args.project_root, config_path=args.config)
    summary = result["summary"]
    print("ECADIN DASHBOARD STAGING: COMPLETED")
    print(f"Region-year rows       : {summary['region_rows']}")
    print(f"National rows          : {summary['national_rows']}")
    print(f"Complete pairs         : {summary['complete_pairs']}")
    print(f"Historical incomplete : {summary['historical_incomplete_pairs']}")
    print(f"Forecast incomplete   : {summary['forecast_incomplete_pairs']}")
    print(f"Staging contracts     : {int(checks['passed'].sum())}/{len(checks)} PASSED")
    print(f"Promoted files        : {promotion['files']}")
    print("Frontend source       : UNCHANGED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
