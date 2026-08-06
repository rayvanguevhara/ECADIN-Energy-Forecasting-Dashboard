from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ecadin_energy.forecasting.configuration import ProductionConfig
from ecadin_energy.forecasting.exceptions import ContractError


def _check(
    rows: list[dict[str, object]],
    *,
    check_id: str,
    passed: bool,
    observed: object,
    expected: object,
    details: str,
) -> None:
    rows.append(
        {
            "check_id": check_id,
            "passed": bool(passed),
            "observed": str(observed),
            "expected": str(expected),
            "details": details,
        }
    )


def validate_production_frames(
    *,
    demand_panel: pd.DataFrame,
    supply_panel: pd.DataFrame,
    demand_backtest: pd.DataFrame,
    supply_backtest: pd.DataFrame,
    demand_forecast: pd.DataFrame,
    supply_forecast: pd.DataFrame,
    accounting: pd.DataFrame,
    combined: pd.DataFrame,
    config: ProductionConfig,
) -> pd.DataFrame:
    checks: list[dict[str, object]] = []
    expected_forecast_rows = (
        config.expected_regions * len(config.forecast_years)
    )
    expected_historical_rows = (
        config.expected_regions * len(config.historical_years)
    )

    panel_ok = (
        len(demand_panel) == expected_historical_rows
        and len(supply_panel) == expected_historical_rows
        and demand_panel["region_id"].nunique() == config.expected_regions
        and supply_panel["region_id"].nunique() == config.expected_regions
    )
    _check(
        checks,
        check_id="canonical_modeling_panels",
        passed=panel_ok,
        observed=f"{len(demand_panel)}/{len(supply_panel)}",
        expected=f"{expected_historical_rows}/{expected_historical_rows}",
        details="Demand and supply panels use the same 34-region annual key grid.",
    )

    expected_demand_predictions = 2448
    demand_backtest_ok = (
        len(demand_backtest) == expected_demand_predictions
        and not demand_backtest.duplicated(
            [
                "protocol",
                "model",
                "region_id",
                "origin_year",
                "forecast_year",
                "horizon",
            ]
        ).any()
    )
    _check(
        checks,
        check_id="demand_backtest_contract",
        passed=demand_backtest_ok,
        observed=len(demand_backtest),
        expected=expected_demand_predictions,
        details="Four baselines; rolling 2019-2024 and recursive origins 2018-2021.",
    )

    expected_supply_predictions = 2436
    supply_backtest_ok = (
        len(supply_backtest) == expected_supply_predictions
        and not supply_backtest.duplicated(
            [
                "protocol",
                "model",
                "region_id",
                "origin_year",
                "forecast_year",
                "horizon",
            ]
        ).any()
    )
    _check(
        checks,
        check_id="supply_backtest_contract",
        passed=supply_backtest_ok,
        observed=len(supply_backtest),
        expected=expected_supply_predictions,
        details="Missing observed DI Yogyakarta generation in 2020 is excluded from validation.",
    )

    forecasts_ok = (
        len(demand_forecast) == expected_forecast_rows
        and len(supply_forecast) == expected_forecast_rows
        and demand_forecast["forecast_gwh"].notna().all()
        and supply_forecast["forecast_gwh"].notna().all()
        and demand_forecast["forecast_gwh"].ge(0).all()
        and supply_forecast["forecast_gwh"].ge(0).all()
    )
    _check(
        checks,
        check_id="production_forecasts",
        passed=forecasts_ok,
        observed=f"{len(demand_forecast)}/{len(supply_forecast)}",
        expected=f"{expected_forecast_rows}/{expected_forecast_rows}",
        details="Demand Drift and supply Drift V1 forecasts for 2025-2030.",
    )

    accounting_ok = (
        len(accounting) == expected_forecast_rows
        and accounting["difference_available"].all()
        and np.allclose(
            accounting["accounting_difference_gwh"],
            accounting["supply_gwh"] - accounting["demand_gwh"],
            rtol=0.0,
            atol=1e-9,
        )
    )
    _check(
        checks,
        check_id="accounting_difference",
        passed=accounting_ok,
        observed=len(accounting),
        expected=expected_forecast_rows,
        details="Accounting difference is local generation minus distributed electricity; it is not an adequacy indicator.",
    )

    expected_combined_rows = (
        expected_historical_rows + expected_forecast_rows
    )
    historical_missing = int(
        (
            combined["data_type"].eq("historical")
            & ~combined["difference_available"]
        ).sum()
    )
    forecast_missing = int(
        (
            combined["data_type"].eq("forecast")
            & ~combined["difference_available"]
        ).sum()
    )
    combined_ok = (
        len(combined) == expected_combined_rows
        and historical_missing == 9
        and forecast_missing == 0
    )
    _check(
        checks,
        check_id="combined_history_forecast",
        passed=combined_ok,
        observed=(
            f"rows={len(combined)}, historical_missing="
            f"{historical_missing}, forecast_missing={forecast_missing}"
        ),
        expected=(
            f"rows={expected_combined_rows}, historical_missing=9, "
            "forecast_missing=0"
        ),
        details="476 historical rows plus 204 forecast rows.",
    )

    result = pd.DataFrame(checks)
    if not result["passed"].all():
        failed = result.loc[~result["passed"]]
        raise ContractError(
            "Production forecasting contracts failed:\\n"
            + failed.to_string(index=False)
        )
    return result


def validate_written_outputs(
    *,
    project_root: str | Path,
    config: ProductionConfig,
) -> pd.DataFrame:
    root = Path(project_root).resolve()
    paths = {
        "demand_panel": root
        / "data/processed/modeling/demand_modeling_panel.csv",
        "supply_panel": root
        / "data/processed/modeling/supply_modeling_panel.csv",
        "demand_backtest": root
        / "outputs/production/backtests/demand_predictions.csv",
        "supply_backtest": root
        / "outputs/production/backtests/supply_predictions.csv",
        "demand_forecast": root
        / "outputs/production/forecasts/demand_forecast.csv",
        "supply_forecast": root
        / "outputs/production/forecasts/supply_forecast.csv",
        "accounting": root
        / "outputs/production/accounting/accounting_difference.csv",
        "combined": root
        / "outputs/production/combined/regional_energy_history_forecast.csv",
    }
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "Production forecasting outputs are missing: " + ", ".join(missing)
        )
    frames = {
        name: pd.read_csv(path, low_memory=False)
        for name, path in paths.items()
    }
    return validate_production_frames(
        demand_panel=frames["demand_panel"],
        supply_panel=frames["supply_panel"],
        demand_backtest=frames["demand_backtest"],
        supply_backtest=frames["supply_backtest"],
        demand_forecast=frames["demand_forecast"],
        supply_forecast=frames["supply_forecast"],
        accounting=frames["accounting"],
        combined=frames["combined"],
        config=config,
    )
