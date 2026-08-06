from __future__ import annotations

from ecadin_energy.data_processing.audit.statistik_listrik_bps import (
    validate_statistik_listrik_bps,
)


def main() -> int:
    result = validate_statistik_listrik_bps()

    print("ECADIN STATISTIK LISTRIK BPS VALIDATION: PASSED")
    print(f"PDF files               : {result['pdf_files']}")
    print(f"Usable text layers      : {result['usable_text_layer_files']}")
    print(
        f"Operational-region PDFs : "
        f"{result['operational_region_publications']}"
    )
    print(f"Province PDFs           : {result['province_publications']}")
    print(f"Latest tables           : {result['latest_tables']}")
    print(f"Regional comparisons    : {result['regional_comparisons']}")
    print(f"Exact matches           : {result['regional_exact_matches']}")
    print(
        f"Revision candidates     : "
        f"{result['regional_revision_candidates']}"
    )
    print(
        f"Missing-vs-zero reviews : "
        f"{result['regional_missing_zero_reviews']}"
    )
    print(f"National total rows     : {result['national_total_rows']}")
    print(
        f"National revisions      : "
        f"{result['national_revision_candidates']}"
    )
    print("Canonical outputs       : UNCHANGED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
