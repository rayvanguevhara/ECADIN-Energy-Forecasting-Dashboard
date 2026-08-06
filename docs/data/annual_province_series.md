# Shared Annual Province-Series Utility

## Purpose

`annual_province_series.py` centralizes the mechanics shared by the distributed
electricity and local generation cleaners.

Shared responsibilities:

- parse numeric values and standard missing markers;
- verify that filename year equals the year inside the source file;
- calculate source SHA-256;
- detect duplicate province rows;
- resolve source province names through the canonical 34-region reference;
- aggregate source aliases to `region_id`;
- write deterministic UTF-8-BOM CSV files;
- replace dataset-specific rows in shared lineage and quality tables;
- format decimal values consistently.

Dataset-specific responsibilities remain in their own modules:

### Distributed electricity

- expected Kalimantan Utara gaps in 2011–2012;
- national-total tolerance of 0.02 GWh;
- 35% consecutive year-on-year review threshold;
- demand-specific output and validation contract.

### Local generation

- DI Yogyakarta missing-value pattern;
- structural modern-Papua source gaps;
- 2013 and 2014 national-total warnings;
- national-total tolerance of 0.10 GWh;
- 75% and 100 GWh year-on-year review thresholds;
- supply-specific output and validation contract.

## Compatibility contract

The refactor must not alter these six outputs:

```text
data/processed/demand/distributed_electricity.csv
data/processed/supply/local_generation.csv
data/processed/master/data_lineage.csv
data/processed/master/data_quality_flags.csv
outputs/reports/data/distributed_electricity_raw_audit.csv
outputs/reports/data/local_generation_raw_audit.csv
```

Run:

```powershell
python .\scripts\verify_shared_cleaner_refactor.py
```

The verifier rebuilds demand first and supply second, then compares SHA-256 and
file size against the pre-refactor baseline.
