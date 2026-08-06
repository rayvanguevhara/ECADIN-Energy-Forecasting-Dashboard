# ECADIN Energy Forecasting

Clean project structure for the ECADIN regional electricity forecasting dashboard.

## Production scope

- Distributed electricity model: Drift
- Local generation model: Drift V1
- Historical period: 2011–2024
- Forecast horizon: 2025–2030
- Modeling geography: 34 harmonized regions
- Dashboard coverage: 2011–2030

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
→ React production build
```

## Important migration rule

The legacy project at `D:\ECADIN Project` remains read-only during migration.
Files are copied selectively; the old project is never moved or deleted until
the clean pipeline passes all production and frontend validation checks.
