# Audit PDF Statistik Listrik BPS

## Scope

This step audits 16 BPS **Statistik Listrik** publications. It is separate
from the ESDM **Statistik Ketenagalistrikan** source.

The audit does not create a replacement historical dataset and does not
overwrite canonical values automatically.

## Publication structure

- 2004–2008 and 2005–2009 use operational-region geography.
- 2006–2010 through 2020–2024 use province geography.
- All 16 PDFs contain usable embedded text, so OCR is not required.

## Latest publication

The detailed reconciliation uses:

`statistik-listrik-2020-2024.pdf`

The latest publication contains 57 tables. Three tables overlap the current
regional canonical variables:

- Table 1: installed capacity
- Table 12: local generation
- Table 30: distributed electricity

## Reconciliation result

Regional comparisons:

- 510 total comparisons
- 478 exact matches
- 30 revision candidates
- 2 missing-versus-zero semantic reviews

Distributed electricity reconciles exactly for all 34 regions and all five
years.

The latest PDF indicates revision candidates concentrated in:

- installed capacity, especially 2021;
- local generation, specifically 2020.

Two canonical missing values are shown as zero in the latest PDF:

- DI Yogyakarta installed capacity, 2020;
- DI Yogyakarta local generation, 2020.

These are review signals only. The audit does not change the canonical CSVs.

## Context-table backlog

High-priority future extraction candidates:

- installed capacity by plant type;
- generation by plant type;
- distributed electricity by customer group.

Medium-priority candidates:

- provincial customer counts by group;
- fuel consumption and operational context.

## Outputs

```text
outputs/reports/data/statistik_listrik_pdf_inventory.csv
outputs/reports/data/statistik_listrik_table_inventory.csv
outputs/reports/data/statistik_listrik_reconciliation.csv
outputs/reports/data/statistik_listrik_national_totals.csv
outputs/reports/data/statistik_listrik_revision_summary.csv
outputs/reports/data/statistik_listrik_bps_build_summary.json
```

## Decision

Keep the existing canonical CSVs unchanged until a deliberate source-revision
policy is approved. The PDF audit is an evidence and reconciliation layer.
