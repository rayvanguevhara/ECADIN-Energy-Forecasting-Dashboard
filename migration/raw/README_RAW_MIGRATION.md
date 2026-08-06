# ECADIN Raw Migration Phase 2A

Inventory analyzed: 316 files.

- copy_raw: 157
- exclude_generated_output: 159
- manual_review: 0

## Policy

Only rows with `Decision=copy_raw` are copied. Legacy `Output` and
`Output Rebuild` folders are intentionally excluded from `data/raw`.

The migration script:

1. keeps the legacy project read-only;
2. verifies source files are below `D:\ECADIN Project`;
3. calculates SHA-256;
4. skips identical content;
5. does not overwrite conflicts without `-Force`;
6. writes a copy manifest.

## Installation

Copy these files into:

`D:\ECADIN_Project_Clean\migration\raw\`

- ECADIN_raw_migration_plan.csv
- ECADIN_raw_source_coverage.csv
- source_registry_seed.csv
- migrate_ecadin_raw_data.ps1

## Dry run

```powershell
cd "D:\ECADIN_Project_Clean"

PowerShell -ExecutionPolicy Bypass `
  -File ".\migration\raw\migrate_ecadin_raw_data.ps1" `
  -DryRun
```

## Actual migration

```powershell
PowerShell -ExecutionPolicy Bypass `
  -File ".\migration\raw\migrate_ecadin_raw_data.ps1"
```

Do not use `-Force` unless a hash conflict has been reviewed.
