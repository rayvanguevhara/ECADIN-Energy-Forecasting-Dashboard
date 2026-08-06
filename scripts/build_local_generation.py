from __future__ import annotations

from ecadin_energy.data_processing.cleaning.local_generation import (
    build_local_generation,
)


def main() -> int:
    summary = build_local_generation()
    print("ECADIN LOCAL GENERATION BUILD: COMPLETED")
    print(f"Source files          : {summary['source_files']}")
    print("Source coverage       : 2011-2015, 2017-2024")
    print(f"Missing source year   : {summary['missing_source_years']}")
    print(f"Model regions         : {summary['model_regions']}")
    print(f"Canonical rows        : {summary['canonical_rows']}")
    print(f"Rows with value       : {summary['canonical_rows_with_value']}")
    print(f"Missing rows          : {summary['canonical_missing_rows']}")
    print(f"Quality flags         : {summary['quality_flags']}")
    print(f"National total alerts : {summary['national_total_mismatch_flags']}")
    print(f"YoY review flags      : {summary['large_yoy_warning_flags']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
