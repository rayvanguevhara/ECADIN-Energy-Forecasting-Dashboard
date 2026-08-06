from __future__ import annotations

from ecadin_energy.data_processing.audit.statistik_listrik_bps import (
    audit_statistik_listrik_bps,
)


def main() -> int:
    result = audit_statistik_listrik_bps()
    counts = result["regional_status_counts"]
    national = result["national_status_counts"]

    print("ECADIN STATISTIK LISTRIK BPS AUDIT: COMPLETED")
    print(f"PDF files               : {result['pdf_files']}")
    print(f"Usable text layers      : {result['usable_text_layer_files']}")
    print(f"Operational-region PDFs : {result['operational_region_publications']}")
    print(f"Province PDFs           : {result['province_publications']}")
    print(f"Latest publication      : {result['latest_publication']}")
    print(f"Latest tables           : {result['latest_table_inventory_rows']}")
    print(f"Regional comparisons    : {result['regional_reconciliation_rows']}")
    print(f"Exact matches           : {counts.get('exact_match', 0)}")
    print(f"Revision candidates     : {counts.get('revision_candidate', 0)}")
    print(
        "Missing-vs-zero reviews : "
        f"{counts.get('canonical_missing_pdf_zero', 0)}"
    )
    print(f"National total rows     : {result['national_total_rows']}")
    print(
        "National revisions      : "
        f"{national.get('revision_candidate', 0)}"
    )
    print("Canonical outputs       : UNCHANGED")
    print("Automatic revision      : NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
