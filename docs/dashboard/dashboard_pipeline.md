# Production Dashboard Data Pipeline

The dashboard pipeline consumes only validated clean-project production outputs.
It does not rerun legacy Phase 3I/3J/3L scripts and does not overwrite finalized
React routes, components, styles, or TypeScript data adapters.

```text
forecast production outputs
→ dashboard staging tables (+ data quality flags & SHA-256 manifests)
→ dynamic dashboard validation (13 cross-consistency & SHA-256 checks)
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
- 9 incomplete historical pairs (`KI`, `KU` 2011–2012; `YO` 2011–2014 & 2020).
- 0 incomplete forecast pairs.
- Demand model: `demand_production_drift` (`Drift`).
- Supply model: `supply_production_national_reconciled_v2` (`National Reconciled Supply`: National Drift over `t >= 2013` reconciled proportionally to FWL step-intervention damped with `break_year = 2021`, `ridge_lambda = 25.0`, `damping_phi = 0.85`).
- Neutral regional accounting difference codes (`gap_category`): `jauh_di_atas_demand`, `di_atas_demand`, `relatif_seimbang`, `di_bawah_demand`, `jauh_di_bawah_demand`, `tidak_tersedia`.
- National YoY growth (`demand_growth_yoy_percent`, `supply_growth_yoy_percent`) is computed on the matched intersection of complete regions across consecutive years (`yoy_common_regions`, `yoy_basis`).
- All 191 structured flags from `data/processed/master/data_quality_flags.csv` are aggregated into `dashboard_data_quality_flags_summary.csv` and exported additively via `quality_flags_summary` and `quality_flags_highlights` in `dashboard-production.json`.
- `dashboard_output_hashes.csv` and `dashboard_input_hashes.csv` provide full SHA-256 verification across staging and production validation.
- `legacy_ridge_used: false` certifies that the pre-project legacy raw-level Ridge regression baseline is not reused (distinct from Supply V2 FWL slope Ridge damping `ridge_lambda = 25.0`).
- Population and per-capita remain backlog and are published as `null`/`N/A`.
- RUPTL remains benchmark/scenario only.
- Accounting difference is not shortage, surplus, reserve margin, or adequacy.

## Frontend safety

The refresh command is allowed to mutate exactly one file:

```text
frontend-dashboard/src/data/dashboard-production.json
```

Every other non-excluded frontend source file (excluding build/cache directories such as `node_modules`, `.output`, `.vercel`, etc.) is hashed before and after refresh. Any change causes the command to fail.
