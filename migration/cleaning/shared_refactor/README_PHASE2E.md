# ECADIN Phase 2E — Shared Cleaner Refactor

This refactor removes duplicated annual-province parsing and deterministic CSV
helpers from the demand and supply cleaners.

## Changes

- Adds `annual_province_series.py`.
- Rewrites both cleaners to consume the shared utility.
- Keeps all dataset-specific rules inside their respective cleaner.
- Improves command output from the misleading `2011-2024` source-year label to
  `2011-2015, 2017-2024`.
- Adds five shared utility tests.
- Preserves all six production output files byte-for-byte.

## Verified result

- Demand canonical rows: 476
- Supply canonical rows: 476
- Unit tests: 10 passed
- Baseline hashes matched: 6 of 6
- Combined cleaner/helper source lines: 1,375 before, 1,281 after

## Install

```powershell
cd "D:\ECADIN_Project_Clean"

PowerShell -ExecutionPolicy Bypass `
  -File ".\migration\cleaning\phase2e_package\install_phase2e_shared_cleaner_refactor.ps1" `
  -ProjectRoot "D:\ECADIN_Project_Clean"
```

## Verify

```powershell
python .\scripts\verify_shared_cleaner_refactor.py

python -m unittest discover `
  -s ".\tests\unit" `
  -p "test_*.py" `
  -v
```
