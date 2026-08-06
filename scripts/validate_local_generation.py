from __future__ import annotations

from ecadin_energy.data_processing.cleaning.local_generation import (
    validate_local_generation,
)


def main() -> int:
    result = validate_local_generation()
    print("ECADIN LOCAL GENERATION VALIDATION: PASSED")
    print(f"Canonical rows        : {result['canonical_rows']}")
    print(f"Regions               : {result['regions']}")
    print(f"Years                 : {result['years']}")
    print(f"Rows with value       : {result['rows_with_value']}")
    print(f"Missing rows          : {result['missing_rows']}")
    print(f"Lineage rows          : {result['lineage_rows']}")
    print(f"Quality flags         : {result['quality_flags']}")
    print(f"National total alerts : {result['national_total_mismatch_flags']}")
    print(f"YoY warnings          : {result['large_yoy_warning_flags']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
