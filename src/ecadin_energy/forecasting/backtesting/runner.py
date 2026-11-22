from __future__ import annotations

import pandas as pd

from ecadin_energy.forecasting.configuration import ProductionConfig
from ecadin_energy.forecasting.evaluation.aggregation import (
    metrics_by_fold,
    metrics_by_horizon,
    metrics_by_region,
    metrics_summary,
)
from ecadin_energy.forecasting.evaluation.challenger import (
    win_rate_by_horizon,
    win_rate_by_regime,
    win_rate_vs_reference,
)
from ecadin_energy.forecasting.models.registry import create_models
from ecadin_energy.forecasting.strategies.one_step import (
    run_one_step_for_model,
)
from ecadin_energy.forecasting.strategies.recursive import (
    run_recursive_for_model,
)


BACKTEST_MODEL_VERSION = "forecasting_core_baselines_v1"


def run_backtests(
    panel: pd.DataFrame,
    config: ProductionConfig,
    *,
    domain: str,
) -> dict[str, pd.DataFrame]:
    rows: list[dict[str, object]] = []
    models = create_models(config.baseline_models)

    for _, region_frame in panel.groupby(
        "region_id",
        sort=False,
    ):
        for model in models:
            rows.extend(
                run_one_step_for_model(
                    region_frame,
                    model=model,
                    domain=domain,
                    model_version=BACKTEST_MODEL_VERSION,
                    reference_baseline=config.reference_baseline,
                    target_years=config.one_step_target_years,
                )
            )
            rows.extend(
                run_recursive_for_model(
                    region_frame,
                    model=model,
                    domain=domain,
                    model_version=BACKTEST_MODEL_VERSION,
                    reference_baseline=config.reference_baseline,
                    origins=config.recursive_origins,
                    max_horizon=config.recursive_max_horizon,
                )
            )

    predictions = pd.DataFrame(rows)
    if predictions.empty:
        raise ValueError(f"No {domain} backtest predictions were produced")
    predictions = predictions.sort_values(
        [
            "protocol",
            "region_id",
            "origin_year",
            "forecast_year",
            "horizon",
            "model",
        ]
    ).reset_index(drop=True)
    return {
        "predictions": predictions,
        "metrics_summary": metrics_summary(predictions),
        "metrics_by_fold": metrics_by_fold(predictions),
        "metrics_by_horizon": metrics_by_horizon(predictions),
        "metrics_by_region": metrics_by_region(predictions),
        "win_rate": win_rate_vs_reference(
            predictions,
            reference_model=config.reference_baseline,
        ),
        "win_rate_by_horizon": win_rate_by_horizon(
            predictions,
            reference_model=config.reference_baseline,
        ),
        "win_rate_by_regime": win_rate_by_regime(
            predictions,
            reference_model=config.reference_baseline,
        ),
    }
