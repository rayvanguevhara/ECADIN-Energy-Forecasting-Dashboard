from __future__ import annotations

from ecadin_energy.data_processing.reference import validate_reference_layer


def main() -> int:
    result = validate_reference_layer()
    print("ECADIN REFERENCE LAYER VALIDATION: PASSED")
    print(f"Regions       : {result['regions']}")
    print(f"Aliases       : {result['aliases']}")
    print(f"Coordinates   : {result['coordinates']}")
    print(f"Bubble-only   : {', '.join(result['bubble_only'])}")
    print(f"Canonical key : {result['canonical_key']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
