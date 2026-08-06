from __future__ import annotations

import numpy as np
import pandas as pd

from ecadin_energy.forecasting.configuration import ProductionConfig


def build_accounting_difference(
    demand_forecast: pd.DataFrame,
    supply_forecast: pd.DataFrame,
    config: ProductionConfig,
) -> pd.DataFrame:
    demand = demand_forecast[
        [
            "region_id",
            "region_name",
            "modeling_order",
            "year",
            "forecast_gwh",
            "model_id",
        ]
    ].rename(
        columns={
            "forecast_gwh": "demand_gwh",
            "model_id": "demand_model_id",
        }
    )
    supply = supply_forecast[
        [
            "region_id",
            "year",
            "forecast_gwh",
            "model_id",
        ]
    ].rename(
        columns={
            "forecast_gwh": "supply_gwh",
            "model_id": "supply_model_id",
        }
    )
    result = demand.merge(
        supply,
        on=["region_id", "year"],
        how="outer",
        validate="one_to_one",
    )
    result["accounting_difference_gwh"] = (
        result["supply_gwh"] - result["demand_gwh"]
    )
    result["difference_abs_gwh"] = result[
        "accounting_difference_gwh"
    ].abs()
    result["supply_to_demand_ratio"] = np.where(
        result["demand_gwh"].eq(0),
        np.nan,
        result["supply_gwh"] / result["demand_gwh"],
    )
    result["difference_to_demand_percent"] = np.where(
        result["demand_gwh"].eq(0),
        np.nan,
        100.0
        * result["accounting_difference_gwh"]
        / result["demand_gwh"],
    )
    result["data_type"] = "forecast"
    result["scenario"] = "production_drift"
    result["accounting_label"] = config.accounting_difference_label
    result["accounting_disclaimer"] = config.accounting_disclaimer
    result["demand_available"] = result["demand_gwh"].notna()
    result["supply_available"] = result["supply_gwh"].notna()
    result["difference_available"] = result[
        "accounting_difference_gwh"
    ].notna()
    return result.sort_values(
        ["modeling_order", "year"]
    ).reset_index(drop=True)


def build_combined_history_forecast(
    demand_panel: pd.DataFrame,
    supply_panel: pd.DataFrame,
    accounting_forecast: pd.DataFrame,
    config: ProductionConfig,
) -> pd.DataFrame:
    demand_history = demand_panel[
        [
            "region_id",
            "region_name",
            "modeling_order",
            "year",
            "training_gwh",
            "target_status",
            "is_interpolated_target",
        ]
    ].rename(
        columns={
            "training_gwh": "demand_gwh",
            "target_status": "demand_status",
            "is_interpolated_target": "demand_interpolated",
        }
    )
    supply_history = supply_panel[
        [
            "region_id",
            "year",
            "training_gwh",
            "target_status",
            "is_interpolated_target",
        ]
    ].rename(
        columns={
            "training_gwh": "supply_gwh",
            "target_status": "supply_status",
            "is_interpolated_target": "supply_interpolated",
        }
    )
    historical = demand_history.merge(
        supply_history,
        on=["region_id", "year"],
        how="outer",
        validate="one_to_one",
    )
    historical["accounting_difference_gwh"] = (
        historical["supply_gwh"] - historical["demand_gwh"]
    )
    historical["data_type"] = "historical"
    historical["scenario"] = "historical_training_series"
    historical["demand_model_id"] = ""
    historical["supply_model_id"] = ""
    historical["accounting_label"] = config.accounting_difference_label
    historical["accounting_disclaimer"] = config.accounting_disclaimer
    historical["demand_available"] = historical["demand_gwh"].notna()
    historical["supply_available"] = historical["supply_gwh"].notna()
    historical["difference_available"] = historical[
        "accounting_difference_gwh"
    ].notna()

    forecast = accounting_forecast.copy()
    forecast["demand_status"] = "forecast"
    forecast["supply_status"] = "forecast"
    forecast["demand_interpolated"] = False
    forecast["supply_interpolated"] = False

    columns = [
        "region_id",
        "region_name",
        "modeling_order",
        "year",
        "data_type",
        "scenario",
        "demand_gwh",
        "supply_gwh",
        "accounting_difference_gwh",
        "demand_available",
        "supply_available",
        "difference_available",
        "demand_status",
        "supply_status",
        "demand_interpolated",
        "supply_interpolated",
        "demand_model_id",
        "supply_model_id",
        "accounting_label",
        "accounting_disclaimer",
    ]
    combined = pd.concat(
        [historical[columns], forecast[columns]],
        ignore_index=True,
    )
    return combined.sort_values(
        ["modeling_order", "year"]
    ).reset_index(drop=True)
