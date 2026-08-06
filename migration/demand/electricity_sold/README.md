# ECADIN Electricity Sold Cleaner

The migration sequence identifier appears only in the ZIP filename. Internal
files and installed project paths use functional names.

## Install

```powershell
cd "D:\ECADIN_Project_Clean"

PowerShell -ExecutionPolicy Bypass `
  -File ".\migration\demand\electricity_sold_package\install_electricity_sold.ps1" `
  -ProjectRoot "D:\ECADIN_Project_Clean"
```

## Build and validate

```powershell
python .\scripts\build_electricity_sold.py
python .\scripts\validate_electricity_sold.py
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
- quality flags: 4
- YoY warnings: 3
- regional master eligibility: false
- deterministic outputs: passed
