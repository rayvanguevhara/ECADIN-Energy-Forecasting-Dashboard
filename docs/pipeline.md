# ECADIN Production Pipeline

The clean project exposes one CLI entry point:

```powershell
python scripts\ecadin.py <command>
```

## Stage commands

```powershell
python scripts\ecadin.py status
python scripts\ecadin.py data build
python scripts\ecadin.py data validate
python scripts\ecadin.py forecast build
python scripts\ecadin.py forecast validate
python scripts\ecadin.py dashboard build
python scripts\ecadin.py dashboard validate
python scripts\ecadin.py frontend validate
python scripts\ecadin.py frontend build --target vercel
python scripts\ecadin.py validate all
```

## End-to-end execution

Run every production stage from raw BPS CSV files through the frontend payload:

```powershell
python scripts\ecadin.py full
```

Include the deployment-target frontend build:

```powershell
python scripts\ecadin.py full `
  --run-frontend-build `
  --frontend-build-target vercel
```

Resume from an already validated canonical master:

```powershell
python scripts\ecadin.py full --start-at forecast
```

Valid resume points are `data`, `forecast`, `dashboard`, and `frontend`.
A resume point does not silently validate or rebuild earlier stages. The caller
is responsible for using only previously validated inputs.

## Data stage order

```text
reference-layer validation
→ distributed electricity build + validation
→ local generation build + validation
→ installed capacity build + validation
→ electricity sold build + validation
→ electricity customers build + validation
→ canonical masters build + validation
```

The data stage does not impute missing source observations and does not mutate
the legacy project.

## Forecast stage

The forecast stage preserves the validated production contract:

```text
demand  : demand_production_drift
supply  : supply_production_drift_v1
period  : 2011–2024 history, 2025–2030 forecast
regions : 34 harmonized modeling regions
```

Only 2016 is interpolated in the modeling panel. The canonical master remains
unchanged. Accounting difference is not an electricity adequacy indicator.

## Dashboard and frontend stages

The dashboard stage creates staging outputs, validates them, promotes them,
validates production, and refreshes only:

```text
frontend-dashboard/src/data/dashboard-production.json
```

TSX, CSS, routes, and components are protected from dashboard refresh.
The frontend release validator checks payload parity, schema, stylesheet, and
Vercel/TanStack Start configuration.

## Reports

Latest orchestration reports are generated under:

```text
outputs/reports/release/
outputs/dashboard/reports/
```

These are generated local artifacts and are excluded from Git.

## Portable test suite

The committed test suite uses deterministic fixtures under `tests/fixtures/`.
It does not require local raw data, `data/processed`, or `outputs/production`.
Therefore a source-only Git checkout can run:

```powershell
python -m unittest discover `
  -s ".\tests" `
  -p "test_*.py" `
  -v
```

The fixture is for automated contract tests only. It is not a replacement for
the local raw-data production pipeline.
