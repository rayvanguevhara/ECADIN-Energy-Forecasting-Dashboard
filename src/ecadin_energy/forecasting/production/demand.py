from __future__ import annotations

import pandas as pd

from ecadin_energy.forecasting.configuration import ProductionConfig
from ecadin_energy.forecasting.models.drift import DriftModel
from ecadin_energy.forecasting.production.common import (
    history_summary,
    training_history,
)
from ecadin_energy.forecasting.strategies.recursive import (
    recursive_forecast_without_actuals,
)


DEMAND_MODEL_VERSION = "demand_production_drift_v1"


def build_demand_forecast(
    panel: pd.DataFrame,
    config: ProductionConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    model = DriftModel()
    summaries = history_summary(panel)
    rows: list[dict[str, object]] = []

    for _, group in panel.groupby("region_id", sort=False):
        history = training_history(group)
        future = recursive_forecast_without_actuals(
            history,
            model=model,
            forecast_years=config.forecast_years,
        )
        summary = summaries.loc[
            summaries["region_id"].eq(group.iloc[0]["region_id"])
        ].iloc[0]
        for record in future.to_dict("records"):
            rows.append(
                {
                    "region_id": str(group.iloc[0]["region_id"]),
                    "region_name": str(group.iloc[0]["region_name"]),
                    "modeling_order": int(
                        group.iloc[0]["modeling_order"]
                    ),
                    "year": int(record["year"]),
                    "forecast_gwh": float(record["prediction_gwh"]),
                    "raw_prediction_gwh": float(
                        record["raw_prediction_gwh"]
                    ),
                    "model_id": config.demand.production_model_id,
                    "model_label": config.demand.model_label,
                    "model_version": DEMAND_MODEL_VERSION,
                    "forecast_type": "recursive_drift_forecast",
                    "origin_year": int(record["origin_year"]),
                    "horizon": int(record["horizon"]),
                    "was_clipped_nonnegative": bool(
                        record["was_clipped_nonnegative"]
                    ),
                    "history_first_year": int(
                        summary["history_first_year"]
                    ),
                    "history_last_year": int(
                        summary["history_last_year"]
                    ),
                    "history_first_gwh": float(
                        summary["history_first_gwh"]
                    ),
                    "history_last_gwh": float(
                        summary["history_last_gwh"]
                    ),
                    "drift_slope_gwh_per_year": float(
                        summary["drift_slope_gwh_per_year"]
                    ),
                }
            )
    forecast = pd.DataFrame(rows).sort_values(
        ["modeling_order", "year"]
    ).reset_index(drop=True)
    return forecast, summaries
