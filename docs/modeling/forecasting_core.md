# ECADIN Modular Production Forecasting Core

## Purpose

This package replaces versioned legacy forecasting scripts with a stable,
testable architecture. Algorithms, feature generation, backtesting, evaluation,
file writing, validation, and orchestration are separated.

## Production contract

```text
Demand target        distributed_electricity_gwh
Demand model         demand_production_drift
Supply target        local_generation_gwh
Supply model         supply_production_drift_v1
Model label          Drift
Historical years     2011–2024
Forecast years       2025–2030
Regions              34
Rolling targets      2019–2024
Recursive origins    2018–2021
Recursive horizon    1–3
RUPTL                 benchmark/scenario only
```

## Architecture

```text
canonical master
  → modeling panels
  → shared split definitions
  → one-step and recursive strategies
  → baseline model registry
  → backtest predictions
  → evaluation and aggregation
  → production Drift forecasts
  → uncertainty calibration
  → accounting difference
  → combined history and forecast
  → production contracts
```

The model classes do not read or write files. The shared backtest runner does
not contain domain-specific formulas. Production artifacts are written only by
the production pipeline.

## Missing-data policy

The canonical master is immutable.

- The source-missing year 2016 is linearly interpolated inside modeling panels
  only when 2015 and 2017 are available.
- Kalimantan Timur and Kalimantan Utara observations before 2013 are excluded
  from training and validation because of the geographic boundary change.
- Other missing source values remain missing.
- Recursive backtests append predictions after the origin and never use future
  actual values.

## Backtesting

Rolling one-step:

```text
target 2019 → train through 2018
...
target 2024 → train through 2023
```

Recursive multi-step:

```text
origins      2018, 2019, 2020, 2021
max horizon  3
```

At horizon 2 and 3, previously generated predictions become history. Actual
future observations are used only after prediction to compute evaluation
metrics.

## Models

The production registry contains the validated Drift implementations.
Baseline challengers are retained for evaluation:

- naive lag-1;
- Drift;
- three-year moving average;
- three-year average growth.

A challenger is never auto-promoted to production.

## Metrics

- macro sMAPE;
- macro MASE;
- micro RMSE;
- aggregate bias;
- challenger win rate versus Drift.

## Accounting disclaimer

The accounting difference compares local generation with distributed
electricity. Interregional electricity flows are omitted. The result must not
be interpreted as shortage, surplus, or adequacy.

## Validation baseline

```text
Demand forecast rows       204
Supply forecast rows       204
Accounting rows            204
Combined rows              680
Historical incomplete        9
Forecast incomplete          0
Production validators       6/6
Legacy parity               6/6
```
