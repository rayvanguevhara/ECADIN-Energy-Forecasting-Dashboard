# ECADIN Dashboard Production Staging

The phase label is used only in the ZIP artifact name. Installed modules and
paths use stable functional names.

## What this package does

- builds dashboard staging tables from validated forecasting production files;
- validates and promotes those tables into `outputs/dashboard/production`;
- generates the React-compatible `dashboard-production.json` contract;
- refreshes exactly one frontend file atomically;
- seeds the finalized React frontend into the clean project only when files are
  missing;
- never runs or installs the legacy frontend integration script.

## Install

```powershell
cd "D:\ECADIN_Project_Clean"

PowerShell -ExecutionPolicy Bypass `
  -File ".\migration\dashboard\dashboard_staging_package\install_dashboard_staging.ps1" `
  -ProjectRoot "D:\ECADIN_Project_Clean"
```

## Build dashboard data and refresh frontend JSON

```powershell
python .\scripts\ecadin.py dashboard build
```

## Validate

```powershell
python .\scripts\ecadin.py dashboard validate
```

## Install frontend dependencies and verify production build

```powershell
cd ".\frontend-dashboard"
npm ci
npm run build
cd ".."
```

After dependencies are installed, the refresh command can include build
verification:

```powershell
python .\scripts\ecadin.py dashboard refresh --run-frontend-build
```

## Production contract

```text
Region-year rows       680
National rows           20
Harmonized regions      34
Complete pairs         671
Historical incomplete    9
Forecast incomplete      0
Demand model            demand_production_drift
Supply model            supply_production_drift_v1
```

Population and per-capita remain backlog and are published as `null` / `N/A`.
RUPTL remains benchmark/scenario only. Accounting difference is not shortage,
surplus, reserve margin, or adequacy.

## Frontend safety

The refresh command may modify only:

```text
frontend-dashboard/src/data/dashboard-production.json
```

All other frontend files are hashed before and after refresh. Existing frontend
source files are preserved by the installer; the packaged frontend is used only
to seed missing files.

## Expected verification

```text
Dashboard staging contracts     9/9 PASSED
Dashboard production contracts  9/9 PASSED
Frontend source safety           3/3 PASSED
Deterministic dashboard outputs 11/11 PASSED
Full clean-project tests        56/56 PASSED
```

The Windows verification completed the TanStack Start/Nitro production build
using the Vercel preset and generated `.vercel/output`. The tracked frontend
payload and dashboard staging evidence use the stable
`ecadin_dashboard_dataset_v1` schema.
