# ECADIN Installed Capacity Cleaner

The migration sequence identifier is used only in the ZIP filename. Source
files, scripts, package folders, and installed project paths use functional
names without a phase prefix.

## Install

```powershell
cd "D:\ECADIN_Project_Clean"

PowerShell -ExecutionPolicy Bypass `
  -File ".\migration\supply\installed_capacity_package\install_installed_capacity.ps1" `
  -ProjectRoot "D:\ECADIN_Project_Clean"
```

## Build and validate

```powershell
python .\scripts\build_installed_capacity.py
python .\scripts\validate_installed_capacity.py
```

## Expected contract

- source files: 13
- source coverage: 2011–2015 and 2017–2024
- canonical regions: 34
- canonical rows: 476
- rows with values: 438
- missing rows: 38
- lineage rows: 13
- quality flags: 74
- national-total mismatch warnings: 2
- large consecutive YoY warnings: 34
- deterministic production outputs: passed

No value is interpolated or silently corrected.
