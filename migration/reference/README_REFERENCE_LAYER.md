# ECADIN Reference Layer — Phase 2B

This package consolidates region identity and harmonization logic from the
validated legacy production artifacts.

## Results

- Canonical model regions: **34**
- Canonical coordinates: **34**
- Region aliases and aggregation rules: **58**
- Demand geography mapping files reviewed: **3 identical files**
- Supply mapping: same source-to-model pairs, different notes only
- Bubble-only legacy geometry: **Kepulauan Riau, Kalimantan Utara, Sulawesi Barat**
- Papua geometry: two legacy GeoJSON features share the canonical `PA` code

## Installed reference files

- `data/reference/regions.csv`
- `data/reference/region_aliases.csv`
- `data/reference/region_coordinates.csv`
- `data/reference/variable_dictionary.csv`
- `data/reference/reference_layer_contract.json`

## Design decisions

1. `region_id + year` is the canonical row key.
2. Canonical masters do not repeat display names, coordinates, source metadata,
   or quality columns.
3. Four modern Papua provinces are aggregated through the alias table, not
   hard-coded separately in each cleaner.
4. GeoJSON is presentation-only and is not the source of canonical region
   identity.
5. PDRB is not yet admitted into the final master schema because its price
   basis and unit still require source audit.

## Install

```powershell
cd "D:\ECADIN_Project_Clean"

PowerShell -ExecutionPolicy Bypass `
  -File ".\migration\reference\reference_layer_package\install_reference_layer.ps1"
```

## Validate

```powershell
python .\scripts\validate_reference_layer.py
```
