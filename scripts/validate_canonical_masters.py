from __future__ import annotations

from ecadin_energy.data_processing.mastering.canonical_masters import (
    validate_canonical_masters,
)


def main() -> int:
    result = validate_canonical_masters()

    print("ECADIN CANONICAL MASTERS VALIDATION: PASSED")
    print(f"Regional rows          : {result['regional_rows']}")
    print(f"Regional complete      : {result['regional_complete_rows']}")
    print(f"Regional incomplete    : {result['regional_incomplete_rows']}")
    print(f"Regional regions       : {result['regional_regions']}")
    print(f"Regional years         : {result['regional_years']}")
    print(f"National rows          : {result['national_rows']}")
    print(f"National complete      : {result['national_complete_rows']}")
    print(f"National incomplete    : {result['national_incomplete_rows']}")
    print(f"Customer groups        : {result['national_customer_groups']}")
    print(f"National years         : {result['national_years']}")
    print(f"Completeness rows      : {result['completeness_rows']}")
    print(f"Input hash rows        : {result['input_hash_rows']}")
    print("Imputation             : NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
