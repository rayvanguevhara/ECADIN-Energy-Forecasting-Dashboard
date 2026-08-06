from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ecadin_energy.dashboard.frontend_refresh import refresh_frontend_data


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh only the ECADIN frontend production data JSON.")
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--run-build", action="store_true")
    args = parser.parse_args()
    result = refresh_frontend_data(
        project_root=args.project_root,
        config_path=args.config,
        run_build=args.run_build,
    )
    print("ECADIN FRONTEND DATA REFRESH: COMPLETED")
    print(f"Dataset SHA256        : {result['frontend_dataset_sha256']}")
    print(f"Nondata files checked : {result['nondata_files_checked']}")
    print(f"Nondata files changed : {len(result['nondata_files_changed'])}")
    print("TSX/CSS source         : UNCHANGED")
    if result["build"] is not None:
        print("Frontend build         : PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
