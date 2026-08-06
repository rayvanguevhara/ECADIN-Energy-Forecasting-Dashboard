# Canonical Masters

## Purpose

This step consolidates already-cleaned canonical datasets into two compact
master tables. It performs deterministic key-based joins only.

No value is interpolated, imputed, forecast, or corrected.

## Regional energy master

Output:

`data/processed/master/regional_energy_master.csv`

Schema:

```text
region_id
year
distributed_electricity_gwh
local_generation_gwh
installed_capacity_mw
```

Contract:

- key: `region_id + year`
- 34 canonical regions
- 2011–2024
- 476 rows
- 432 rows complete across all three variables
- 44 rows contain at least one source-level missing value

Expected source-level missing counts:

- distributed electricity: 36
- local generation: 39
- installed capacity: 38

The 2016 row is blank for all three variables and all 34 regions. Additional
source gaps remain visible for Kalimantan Utara and DI Yogyakarta.

## National customer-group master

Output:

`data/processed/master/national_customer_group_master.csv`

Schema:

```text
year
customer_group_id
electricity_sold_gwh
electricity_customers_count
```

Contract:

- key: `year + customer_group_id`
- 5 canonical customer groups
- 1995–2024
- 150 rows
- 145 complete rows
- five incomplete rows, all in 2016

This table is national and is not joined to the regional master.

## Supporting reports

- `outputs/reports/data/canonical_master_completeness.csv`
- `outputs/reports/data/canonical_master_input_hashes.csv`
- `outputs/reports/data/canonical_master_build_summary.json`

The input-hash report records the exact canonical and reference files used to
build the masters.

## Quality policy

Source-specific quality flags remain authoritative in:

`data/processed/master/data_quality_flags.csv`

This master builder does not duplicate or modify those flags.
