# Local Generation Cleaner

## Purpose

Build a compact canonical local-generation table from annual BPS province CSV
files.

## Input

`data/raw/bps/local_generation/*.csv`

Observed files cover 2011–2015 and 2017–2024. The 2016 file is unavailable.

## Canonical output

`data/processed/supply/local_generation.csv`

Columns:

```text
region_id
year
local_generation_gwh
```

The output contains 34 regions × 14 years = 476 rows.

## Missing-value contract

- 34 blank rows in 2016 because the annual source file is unavailable.
- DI Yogyakarta is blank in 2011, 2012, 2013, 2014, and 2020.
- Four modern Papua province rows are structural blanks before 2023 and do not
  make the canonical Papua/Papua Barat aggregate blank because parent-region
  values are available.

## National total audit

The canonical total is the sum of province rows. The reported Indonesia total
is retained for audit only.

- 2013: reported 22,206.93 GWh versus province sum 222,206.92 GWh.
- 2014: reported 238,019.10 GWh versus province sum 238,009.02 GWh.
- These mismatches are flagged; province values are not corrected.

## Supporting outputs

- `data/processed/master/data_lineage.csv`
- `data/processed/master/data_quality_flags.csv`
- `outputs/reports/data/local_generation_raw_audit.csv`
- `outputs/reports/data/local_generation_build_summary.json`

## Quality policy

- Differences up to 0.10 GWh are treated as rounding.
- National mismatches above 0.10 GWh are warnings.
- Consecutive changes of at least 75% and 100 GWh are flagged for review.
- No source value is changed, imputed, or forecast in the canonical layer.
