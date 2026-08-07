# Portable contract fixtures

These files make the automated test suite runnable from a source-only checkout.
They are test evidence, not production inputs.

## Forecasting master fixture

`forecasting/regional_energy_master.csv` contains the validated 34-region,
2011–2024 demand and local-generation history required by forecasting contract
tests.

- Observed source values are preserved.
- The 2016 source values remain blank so the production modeling policy performs
  its explicit 2016 interpolation.
- Non-2016 unavailable values remain blank.
- `installed_capacity_mw` is intentionally blank because the production demand
  and supply models do not consume it.

## Production output fixtures

The files under `production/` are the minimal validated outputs required to test
forecast and dashboard contracts without committing the generated
`outputs/production` directory.

Do not copy these fixtures into `data/processed` for a real production run.
