# ECADIN Phase 2D — Local Generation Cleaner

## Install

```powershell
cd "D:\ECADIN_Project_Clean"

PowerShell -ExecutionPolicy Bypass `
  -File ".\migration\supply\phase2d_package\install_phase2d_local_generation.ps1" `
  -ProjectRoot "D:\ECADIN_Project_Clean"
```

## Build and validate

```powershell
python .\scripts\build_local_generation.py
python .\scripts\validate_local_generation.py
```

## Expected contract

- source files: 13
- canonical regions: 34
- canonical years: 2011–2024
- canonical rows: 476
- rows with values: 437
- missing rows: 39
- lineage rows: 13
- quality flags: 66
- national total mismatch warnings: 2
- large consecutive YoY warnings: 25

No source value is silently corrected.
