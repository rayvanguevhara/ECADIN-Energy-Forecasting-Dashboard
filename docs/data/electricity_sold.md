# Electricity Sold Cleaner

## Geographic scope

The raw BPS table is a **national customer-group series**, not a province
series. It must not be joined to a regional `region_id + year` master.

## Input

`data/raw/bps/electricity_sold/*.csv`

Observed years are 1995–2015 and 2017–2024. The 2016 source file is
unavailable.

## Canonical outputs

Customer-group detail:

`data/processed/demand/electricity_sold_by_customer_group.csv`

```text
year
customer_group_id
electricity_sold_gwh
```

National total:

`data/processed/demand/electricity_sold_total.csv`

```text
year
electricity_sold_gwh
```

The detail table contains 5 customer groups × 30 years = 150 rows. Five rows
are blank in 2016. The total table contains 30 rows with one blank row in
2016.

## Customer-group reference

`data/reference/customer_groups.csv`

The source typo `Bussiness` is mapped to canonical ID `business` and display
name `Business`. Source values are unchanged.

## Total reconciliation

`All Customer` is compared with the sum of Social, Households, Business,
Industry, and Public. All 29 observed files reconcile within 0.01 GWh.
Eight years contain only a ±0.01 GWh rounding difference.

## Quality warnings

Consecutive changes are flagged when both conditions hold:

- absolute year-on-year change is at least 20%; and
- absolute change is at least 500 GWh.

Warnings are generated for Business in 1996 and Public in 2004 and 2024.
No reported value is modified.

## Master eligibility

This dataset is useful for national overview, demand composition, and
historical validation. It is not eligible as a direct feature in the
province-level master because it has no province dimension.
