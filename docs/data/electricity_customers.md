# Electricity Customers Cleaner

## Geographic scope

The raw BPS table is a **national customer-group series**, not a province
series. It must not be joined directly to the regional `region_id + year`
master.

## Dependencies

This cleaner reuses:

- `annual_category_series.py`
- `data/reference/customer_groups.csv`

Both were introduced by the electricity-sold cleaner.

## Input

`data/raw/bps/electricity_customers/*.csv`

Observed years are 1995–2015 and 2017–2024. The 2016 source file is
unavailable.

## Canonical outputs

Customer-group detail:

`data/processed/demand/electricity_customers_by_customer_group.csv`

```text
year
customer_group_id
electricity_customers_count
```

National total:

`data/processed/demand/electricity_customers_total.csv`

```text
year
electricity_customers_count
```

The detail table contains 5 customer groups × 30 years = 150 rows. Five rows
are blank in 2016. The total table contains 30 rows with one blank row in
2016.

## Customer-group reference

The source label `Bussiness` maps to canonical ID `business`. Counts are
retained exactly as reported.

## Total reconciliation

Every observed `All Customer` value exactly equals the sum of Social,
Households, Business, Industry, and Public. Counts are required to be
non-negative integers.

## Quality warnings

Consecutive changes are flagged when both conditions hold:

- absolute year-on-year change is at least 20%; and
- absolute change is at least 100,000 customers.

Warnings are generated for Business in 2018 and Public in 2024. No source
value is modified.

## Master eligibility

This dataset is suitable for national overview, customer-composition
analysis, and demand context. It is not eligible as a direct feature in the
province-level master because it has no province dimension.
