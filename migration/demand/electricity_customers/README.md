# ECADIN Electricity Customers Cleaner

The migration sequence identifier appears only in the ZIP filename. Internal
files and installed project paths use functional names.

## Required prior files

```text
src/ecadin_energy/data_processing/cleaning/annual_category_series.py
data/reference/customer_groups.csv
```

## Install

```powershell
cd "D:\ECADIN_Project_Clean"

PowerShell -ExecutionPolicy Bypass `
  -File ".\migration\demand\electricity_customers_package\install_electricity_customers.ps1" `
  -ProjectRoot "D:\ECADIN_Project_Clean"
```

## Build and validate

```powershell
python .\scripts\build_electricity_customers.py
python .\scripts\validate_electricity_customers.py
```

## Expected contract

- geographic scope: National
- source files: 29
- source coverage: 1995–2015 and 2017–2024
- customer groups: 5
- detail rows: 150
- detail rows with values: 145
- total rows: 30
- total rows with values: 29
- lineage rows: 29
- quality flags: 3
- national-total mismatch warnings: 0
- YoY warnings: 2
- regional master eligibility: false
- deterministic outputs: passed
