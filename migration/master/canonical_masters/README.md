# ECADIN Canonical Masters

The migration sequence identifier appears only in the ZIP filename. Internal
files and installed project paths use functional names.

## Required canonical inputs

```text
data/processed/demand/distributed_electricity.csv
data/processed/supply/local_generation.csv
data/processed/supply/installed_capacity.csv
data/processed/demand/electricity_sold_by_customer_group.csv
data/processed/demand/electricity_customers_by_customer_group.csv
data/reference/regions.csv
data/reference/customer_groups.csv
```

## Install

```powershell
cd "D:\ECADIN_Project_Clean"

PowerShell -ExecutionPolicy Bypass `
  -File ".\migration\master\canonical_masters_package\install_canonical_masters.ps1" `
  -ProjectRoot "D:\ECADIN_Project_Clean"
```

## Build and validate

```powershell
python .\scripts\build_canonical_masters.py
python .\scripts\validate_canonical_masters.py
```

## Expected contract

- regional master: 476 rows
- regional complete rows: 432
- regional incomplete rows: 44
- national customer-group master: 150 rows
- national complete rows: 145
- national incomplete rows: 5
- completeness audit: 44 rows
- input hashes: 7 rows
- imputation: none
- deterministic outputs: passed
