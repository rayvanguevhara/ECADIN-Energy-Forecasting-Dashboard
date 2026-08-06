from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ecadin_energy.pipeline.dashboard import run_dashboard_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ECADIN dashboard production pipeline.")
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--skip-frontend-refresh", action="store_true")
    parser.add_argument("--run-frontend-build", action="store_true")
    args = parser.parse_args()
    result = run_dashboard_pipeline(
        project_root=args.project_root,
        config_path=args.config,
        refresh_frontend=not args.skip_frontend_refresh,
        run_frontend_build=args.run_frontend_build,
    )
    print("ECADIN DASHBOARD PRODUCTION PIPELINE: COMPLETED")
    print(f"Region-year rows      : {result['staging']['region_rows']}")
    print(f"Production contracts : {int(result['production_checks']['passed'].sum())}/{len(result['production_checks'])} PASSED")
    print("Frontend refresh      : " + ("COMPLETED" if result['frontend'] else "SKIPPED"))
    if result['frontend'] and result['frontend']['build'] is not None:
        print("Frontend build        : PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
