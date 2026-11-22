from __future__ import annotations

import numpy as np
import pandas as pd

from ecadin_energy.dashboard.configuration import DashboardConfig
from ecadin_energy.dashboard.contracts import DashboardContractError
from ecadin_energy.forecasting.configuration import ProductionConfig


def _extract_protocol_metrics(
    side_rows: pd.DataFrame,
    protocol_name: str,
) -> tuple[object, float, float, float, float]:
    if "protocol" not in side_rows.columns:
        return (pd.NA, np.nan, np.nan, np.nan, np.nan)
    matched = side_rows.loc[side_rows["protocol"].astype(str).eq(protocol_name)]
    if matched.empty:
        return (pd.NA, np.nan, np.nan, np.nan, np.nan)
    row = matched.iloc[0]
    pred_count = pd.to_numeric(row.get("prediction_count"), errors="coerce")
    return (
        int(pred_count) if pd.notna(pred_count) else pd.NA,
        float(pd.to_numeric(row.get("macro_smape_percent"), errors="coerce")),
        float(pd.to_numeric(row.get("macro_mase"), errors="coerce")),
        float(pd.to_numeric(row.get("micro_rmse_gwh"), errors="coerce")),
        float(pd.to_numeric(row.get("aggregate_bias_percent"), errors="coerce")),
    )


def build_model_summary(
    models: pd.DataFrame,
    config: DashboardConfig,
    *,
    forecast_config: ProductionConfig | None = None,
) -> pd.DataFrame:
    """Build dashboard model summary preserving legacy columns and adding V2 metrics/params."""
    selected = models.loc[
        models["selected_for_production"].astype(str).str.lower().eq("true")
    ].copy()
    rows: list[dict[str, object]] = []
    for side in ("demand", "supply"):
        side_rows = selected.loc[selected["domain"].eq(side)]
        if side_rows.empty:
            raise DashboardContractError(f"Production model missing for {side}")
        model_ids = sorted(side_rows["production_model_id"].astype(str).unique())
        if len(model_ids) != 1:
            raise DashboardContractError(
                f"Multiple production model IDs for {side}: {model_ids}"
            )
        model_id = model_ids[0]

        domain_cfg = forecast_config.domain_config(side) if forecast_config is not None else None
        if domain_cfg is not None and domain_cfg.production_model_id == model_id:
            active_model = domain_cfg.model_name
            evaluated_model_count = len(forecast_config.evaluated_models_for_domain(side))
        else:
            active_model = (
                "national_reconciled_supply"
                if "national_reconciled" in model_id
                else "drift"
            )
            if forecast_config is not None:
                evaluated_model_count = len(forecast_config.baseline_models)
            else:
                evaluated_model_count = 5 if active_model == "national_reconciled_supply" else 4

        label_series = (
            side_rows["model_label"].dropna().astype(str).str.strip()
            if "model_label" in side_rows.columns
            else pd.Series([], dtype="string")
        )
        if not label_series.empty and label_series.iloc[0]:
            model_label = str(label_series.iloc[0])
        elif domain_cfg is not None and domain_cfg.production_model_id == model_id:
            model_label = domain_cfg.model_label
        elif active_model == "national_reconciled_supply":
            model_label = "National Reconciled Supply (Drift National -> Step Intervention Damped)"
        else:
            model_label = "Drift"

        domain_desc = (
            "Distributed-electricity" if side == "demand" else "Local-generation"
        )
        note = (
            f"{domain_desc} production forecast from validated "
            f"{model_label} ({model_id}) outputs."
        )

        (
            rolling_count,
            rolling_smape,
            rolling_mase,
            rolling_rmse,
            rolling_bias,
        ) = _extract_protocol_metrics(side_rows, "rolling_one_step")
        (
            recursive_count,
            recursive_smape,
            recursive_mase,
            recursive_rmse,
            recursive_bias,
        ) = _extract_protocol_metrics(side_rows, "recursive_multi_step")

        params = (
            domain_cfg.model_params
            if domain_cfg is not None
            and domain_cfg.production_model_id == model_id
            and active_model == "national_reconciled_supply"
            else None
        )
        rows.append(
            {
                "side": side,
                "active_model": active_model,
                "model_version": model_id,
                "status": "production",
                "forecast_period": f"{config.forecast_start_year}-{config.forecast_end_year}",
                "geography": config.modeling_geography,
                "selection_basis": "validated production contract",
                "legacy_model_reused": config.legacy_model_reused,
                "regional_uncertainty_display_allowed": config.regional_uncertainty_display_allowed,
                "note": note,
                "model_label": model_label,
                "evaluated_backtest_model_count": evaluated_model_count,
                "rolling_prediction_count": rolling_count,
                "rolling_macro_smape_percent": rolling_smape,
                "rolling_macro_mase": rolling_mase,
                "rolling_micro_rmse_gwh": rolling_rmse,
                "rolling_aggregate_bias_percent": rolling_bias,
                "recursive_prediction_count": recursive_count,
                "recursive_macro_smape_percent": recursive_smape,
                "recursive_macro_mase": recursive_mase,
                "recursive_micro_rmse_gwh": recursive_rmse,
                "recursive_aggregate_bias_percent": recursive_bias,
                "break_year": int(params.break_year) if params is not None else pd.NA,
                "ridge_lambda": float(params.ridge_lambda) if params is not None else np.nan,
                "damping_phi": float(params.damping_phi) if params is not None else np.nan,
                "national_start_year": (
                    int(params.national_start_year) if params is not None else pd.NA
                ),
            }
        )

    frame = pd.DataFrame(rows)
    for col in (
        "evaluated_backtest_model_count",
        "rolling_prediction_count",
        "recursive_prediction_count",
        "break_year",
        "national_start_year",
    ):
        frame[col] = pd.array(frame[col].tolist(), dtype="Int64")
    return frame
