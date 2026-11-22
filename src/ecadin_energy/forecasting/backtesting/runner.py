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
from ecadin_energy.forecasting.evaluation.metrics import build_forecast_record
from ecadin_energy.forecasting.models.registry import (
    create_models,
    create_panel_model,
    is_panel_model,
)
from ecadin_energy.forecasting.strategies.one_step import (
    history_at_origin,
    run_one_step_for_model,
)
from ecadin_energy.forecasting.strategies.recursive import (
    run_recursive_for_model,
)


BACKTEST_MODEL_VERSION = "forecasting_core_baselines_v1"


def _run_panel_model_backtest(
    panel: pd.DataFrame,
    config: ProductionConfig,
    *,
    domain: str,
    model_id: str,
) -> list[dict[str, object]]:
    """Run leak-free rolling_one_step and recursive_multi_step for a panel model."""
    domain_config = config.domain_config(domain)
    panel_model = create_panel_model(
        model_id,
        params=domain_config.model_params,
        model_label=domain_config.model_label,
    )
    region_frames: dict[str, pd.DataFrame] = {
        str(rid): group.sort_values("year").reset_index(drop=True)
        for rid, group in panel.groupby("region_id", sort=False)
    }
    region_ids = tuple(region_frames.keys())
    region_names = {
        rid: str(frame.iloc[0]["region_name"])
        for rid, frame in region_frames.items()
    }
    actual_lookups = {
        rid: frame.set_index("year")["actual_gwh"].to_dict()
        for rid, frame in region_frames.items()
    }
    eligible_lookups = {
        rid: frame.set_index("year")["validation_eligible"].to_dict()
        for rid, frame in region_frames.items()
    }

    rows: list[dict[str, object]] = []
    for target_year in config.one_step_target_years:
        target = int(target_year)
        origin = target - 1
        panel_hist = panel.loc[
            panel["year"].le(origin)
            & panel["training_eligible"]
            & panel["training_gwh"].notna()
        ].copy()
        pred_map = panel_model.forecast_panel(
            panel_hist,
            origin,
            (target,),
            region_ids,
        )
        for region_id in region_ids:
            is_eligible = bool(eligible_lookups[region_id].get(target, False))
            actual = actual_lookups[region_id].get(target)
            if not is_eligible or pd.isna(actual):
                continue
            scale_history = history_at_origin(region_frames[region_id], origin)
            rows.append(
                build_forecast_record(
                    domain=domain,
                    model_version=domain_config.production_model_id,
                    protocol="rolling_one_step",
                    model=panel_model.model_id,
                    reference_baseline=config.reference_baseline,
                    region_id=region_id,
                    region_name=region_names[region_id],
                    origin_year=origin,
                    forecast_year=target,
                    horizon=1,
                    history_for_scale=scale_history,
                    actual=float(actual),
                    raw_prediction=float(pred_map[(region_id, target)]),
                ).as_dict()
            )

    horizons = tuple(range(1, config.recursive_max_horizon + 1))
    for origin_year in config.recursive_origins:
        origin = int(origin_year)
        forecast_years = tuple(origin + h for h in horizons)
        panel_hist = panel.loc[
            panel["year"].le(origin)
            & panel["training_eligible"]
            & panel["training_gwh"].notna()
        ].copy()
        pred_map = panel_model.forecast_panel(
            panel_hist,
            origin,
            forecast_years,
            region_ids,
        )
        for region_id in region_ids:
            scale_history = history_at_origin(region_frames[region_id], origin)
            for horizon in horizons:
                target = origin + horizon
                is_eligible = bool(
                    eligible_lookups[region_id].get(target, False)
                )
                actual = actual_lookups[region_id].get(target)
                if not is_eligible or pd.isna(actual):
                    continue
                rows.append(
                    build_forecast_record(
                        domain=domain,
                        model_version=domain_config.production_model_id,
                        protocol="recursive_multi_step",
                        model=panel_model.model_id,
                        reference_baseline=config.reference_baseline,
                        region_id=region_id,
                        region_name=region_names[region_id],
                        origin_year=origin,
                        forecast_year=target,
                        horizon=horizon,
                        history_for_scale=scale_history,
                        actual=float(actual),
                        raw_prediction=float(pred_map[(region_id, target)]),
                    ).as_dict()
                )
    return rows


def run_backtests(
    panel: pd.DataFrame,
    config: ProductionConfig,
    *,
    domain: str,
) -> dict[str, pd.DataFrame]:
    rows: list[dict[str, object]] = []
    evaluated_models = config.evaluated_models_for_domain(domain)
    series_model_ids = [m for m in evaluated_models if not is_panel_model(m)]
    panel_model_ids = [m for m in evaluated_models if is_panel_model(m)]
    models = create_models(series_model_ids)

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

    for panel_model_id in panel_model_ids:
        rows.extend(
            _run_panel_model_backtest(
                panel,
                config,
                domain=domain,
                model_id=panel_model_id,
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
