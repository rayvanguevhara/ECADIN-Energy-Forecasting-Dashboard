# ECADIN Forecasting Core

The ZIP phase label is not used in installed Python modules or project paths.

## Contents

This package installs:

- modular forecasting source code;
- production configuration;
- thin CLI scripts;
- unit, integration, and contract tests;
- audit and parity evidence.

It does **not** modify the canonical master during installation. Production
outputs are generated only when the build command is run.

## Prerequisites

```powershell
cd "D:\ECADIN_Project_Clean"

python -m pip install -r `
  ".\migration\forecasting\forecasting_core_package\requirements_forecasting.txt"
```

## Install

```powershell
PowerShell -ExecutionPolicy Bypass `
  -File ".\migration\forecasting\forecasting_core_package\install_forecasting_core.ps1" `
  -ProjectRoot "D:\ECADIN_Project_Clean"
```

## Build

```powershell
python .\scripts\ecadin.py forecast build
```

Equivalent direct command:

```powershell
python .\scripts\run_production_forecast.py
```

## Validate

```powershell
python .\scripts\ecadin.py forecast validate
```

Equivalent direct command:

```powershell
python .\scripts\validate_production_forecast.py
```

## Compare with legacy production baseline

The old project remains read-only.

```powershell
python .\scripts\compare_legacy_forecasting_baseline.py `
  --project-root "D:\ECADIN_Project_Clean" `
  --legacy-root "D:\ECADIN Project"
```

Expected result:

```text
Legacy parity: 6/6 PASSED
```

## Tests

Focused forecasting tests:

```powershell
python -m unittest `
  tests.unit.test_forecasting_panels `
  tests.unit.test_lag_features `
  tests.unit.test_drift_models `
  tests.unit.test_backtest_splits `
  tests.unit.test_recursive_forecast `
  tests.unit.test_metrics `
  tests.integration.test_production_forecasting_pipeline `
  tests.contracts.test_forecasting_output_contract `
  -v
```

Full clean-project test suite:

```powershell
python -m unittest discover `
  -s ".\tests" `
  -p "test_*.py" `
  -v
```

## Expected production output

```text
Demand backtest rows    2448
Supply backtest rows    2436
Demand forecast rows     204
Supply forecast rows     204
Accounting rows          204
Combined rows            680
Historical incomplete      9
Forecast incomplete        0
Production contracts      6/6
```

## Cleanup after successful installation

Delete only the temporary extracted package:

```powershell
Remove-Item `
  ".\migration\forecasting\forecasting_core_package" `
  -Recurse `
  -Force `
  -ErrorAction SilentlyContinue
```

Keep:

```text
migration/forecasting/core/
```

It contains the permanent audit, parity, contract, and migration evidence.
