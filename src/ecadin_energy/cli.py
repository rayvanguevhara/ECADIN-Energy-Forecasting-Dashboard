from __future__ import annotations

import argparse
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ecadin",
        description="ECADIN clean-project command line interface.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="Show clean-project initialization status.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "status":
        root = Path(__file__).resolve().parents[2]
        print("ECADIN clean project initialized")
        print(f"Project root : {root}")
        print("Pipeline     : scaffold only; production modules not migrated yet")
        print("Legacy root  : D:\\ECADIN Project (read-only during migration)")
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
