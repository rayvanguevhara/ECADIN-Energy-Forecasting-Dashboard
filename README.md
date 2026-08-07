# ECADIN Energy Forecasting

Clean monorepo for the ECADIN regional electricity forecasting dashboard.

## Production scope

- Distributed electricity model: Drift
- Local generation model: Drift V1
- Historical period: 2011–2024
- Forecast horizon: 2025–2030
- Modeling geography: 34 harmonized regions
- Dashboard coverage: 2011–2030
- Frontend deployment target: Vercel with TanStack Start/Nitro

## Canonical flow

```text
raw data
→ extraction and cleaning
→ harmonized canonical masters
→ demand Drift
→ supply Drift V1
→ accounting difference
→ combined historical and forecast dataset
→ dashboard staging and validation
→ frontend JSON refresh
→ Vercel production build
```

## Main commands

```powershell
python scripts\ecadin.py status
python scripts\ecadin.py data build
python scripts\ecadin.py forecast build
python scripts\ecadin.py dashboard build
python scripts\ecadin.py frontend validate
python scripts\ecadin.py validate all
python scripts\ecadin.py full --run-frontend-build
```

See `docs/pipeline.md` for stage order, resume behavior, and release checks.

## Portable tests

The test suite is self-contained and does not require ignored raw or generated
production files:

```powershell
python -m unittest discover -s ".\tests" -p "test_*.py" -v
```

The deterministic files under `tests/fixtures` are test-only evidence. Real
production runs continue to use local raw data and generated canonical masters.
