from __future__ import annotations

from ecadin_energy.data_processing.cleaning.electricity_sold import (
    build_electricity_sold,
)


def main() -> int:
    summary = build_electricity_sold()
    print("ECADIN ELECTRICITY SOLD BUILD: COMPLETED")
    print(f"Geographic scope       : {summary['geographic_scope']}")
    print(f"Source files           : {summary['source_files']}")
    print(f"Source coverage        : {summary['source_coverage']}")
    print(f"Missing source year    : {summary['missing_source_years']}")
    print(f"Customer groups        : {summary['customer_groups']}")
    print(f"Detail rows            : {summary['detail_rows']}")
    print(f"Detail rows with value : {summary['detail_rows_with_value']}")
    print(f"Detail missing rows    : {summary['detail_missing_rows']}")
    print(f"Total rows             : {summary['total_rows']}")
    print(f"Quality flags          : {summary['quality_flags']}")
    print(f"YoY review flags       : {summary['large_yoy_warning_flags']}")
    print(f"Regional master        : NOT ELIGIBLE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
