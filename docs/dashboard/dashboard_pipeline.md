# Production Dashboard Data Pipeline

The dashboard pipeline consumes only validated clean-project production outputs.
It does not rerun legacy Phase 3I/3J/3L scripts and does not overwrite finalized
React routes, components, styles, or TypeScript data adapters.

```text
forecast production outputs
→ dashboard staging tables
→ dashboard validation
→ controlled production promotion
→ dashboard-production.json
→ atomic frontend data refresh
→ optional npm production build
```

## Stable contracts

- 34 harmonized regions.
- 2011–2024 historical period.
- 2025–2030 production forecast period.
- 680 region-year rows.
- 671 complete accounting pairs.
- 9 incomplete historical pairs.
- 0 incomplete forecast pairs.
- Demand model: `demand_production_drift`.
- Supply model: `supply_production_drift_v1`.
- Population and per-capita remain backlog and are published as `null`/`N/A`.
- RUPTL remains benchmark/scenario only.
- Accounting difference is not shortage, surplus, reserve margin, or adequacy.

## Frontend safety

The refresh command is allowed to mutate exactly one file:

```text
frontend-dashboard/src/data/dashboard-production.json
```

Every other frontend source file is hashed before and after refresh. Any change
causes the command to fail.
