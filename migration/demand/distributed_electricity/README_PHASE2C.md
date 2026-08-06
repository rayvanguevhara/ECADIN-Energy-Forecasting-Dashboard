# ECADIN Phase 2C — Distributed Electricity Cleaner

This package installs the first rewritten canonical data cleaner.

## Install

```powershell
cd "D:\ECADIN_Project_Clean"

PowerShell -ExecutionPolicy Bypass `
  -File ".\migration\demand\phase2c_package\install_phase2c_distributed_electricity.ps1" `
  -ProjectRoot "D:\ECADIN_Project_Clean"
```

## Build

```powershell
python .\scripts\build_distributed_electricity.py
```

## Validate

```powershell
python .\scripts\validate_distributed_electricity.py
```

## Expected production contract

- source files: 13
- observed years: 2011–2015 and 2017–2024
- canonical regions: 34
- canonical years: 2011–2024
- canonical rows: 476
- rows with values: 440
- explicit missing rows: 36; 34 in 2016 and Kalimantan Utara in 2011–2012
- lineage rows: 13
- large consecutive YoY warnings: 7

No raw value is corrected, interpolated, or overwritten.
