# Distributed Electricity Cleaner

## Purpose

Build a compact canonical distributed-electricity table from the annual BPS
CSV files.

## Input

`data/raw/bps/distributed_electricity/*.csv`

Expected source files:

- 2011–2015
- 2017–2024
- 2016 is explicitly unavailable

## Canonical output

`data/processed/demand/distributed_electricity.csv`

Columns:

```text
region_id
year
distributed_electricity_gwh
```

The output contains 34 regions × 14 years = 476 rows. All 34 rows for 2016 contain a blank value. Kalimantan Utara is also blank in 2011–2012 because the annual source rows contain dash values. The cleaner does not interpolate.

## Supporting outputs

- `data/processed/master/data_lineage.csv`
- `data/processed/master/data_quality_flags.csv`
- `outputs/reports/data/distributed_electricity_raw_audit.csv`
- `outputs/reports/data/distributed_electricity_build_summary.json`

## Quality policy

- Source totals are reconciled against the Indonesia total with a 0.02 GWh
  tolerance for rounding.
- Missing 2016 values remain missing.
- Consecutive year-on-year changes of at least 35% are flagged for review.
- Warning values are retained exactly as reported.
- Imputation and feature engineering belong to the modeling-panel layer, not
  the canonical source table.
