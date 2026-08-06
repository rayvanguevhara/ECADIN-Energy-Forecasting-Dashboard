# Installed Capacity Cleaner

## Input

`data/raw/bps/installed_capacity/*.csv`

Observed source years are 2011–2015 and 2017–2024. The 2016 source file is
unavailable.

## Canonical output

`data/processed/supply/installed_capacity.csv`

```text
region_id
year
installed_capacity_mw
```

The canonical table contains 34 regions × 14 years = 476 rows.

## Missing-value contract

- All 34 model regions are blank in 2016.
- DI Yogyakarta is blank in 2017, 2018, 2019, and 2020 because the province
  row is reported as `-`.
- Four modern Papua province rows are structural blanks before 2023. They do
  not make the canonical Papua or Papua Barat values blank because the
  corresponding parent-region values remain available.
- No interpolation is performed in the canonical layer.

## National-total audit

The canonical national total is calculated from the reported province rows.

- 2013: reported total 45,476.31 MW; province sum 45,467.31 MW;
  difference -9.00 MW.
- 2017: reported total 58,163.33 MW; province sum 56,892.91 MW;
  difference -1,270.42 MW.
- Differences up to 0.10 MW are classified as rounding differences.
- Mismatched totals are flagged; province values are not corrected.

## Supporting outputs

- `data/processed/master/data_lineage.csv`
- `data/processed/master/data_quality_flags.csv`
- `outputs/reports/data/installed_capacity_raw_audit.csv`
- `outputs/reports/data/installed_capacity_build_summary.json`

## Change warnings

A consecutive year-on-year change is flagged when both conditions hold:

- absolute percentage change is at least 75%; and
- absolute capacity change is at least 100 MW.

Warnings do not modify source values.
