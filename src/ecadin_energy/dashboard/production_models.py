from __future__ import annotations

import pandas as pd

from ecadin_energy.dashboard.configuration import DashboardConfig
from ecadin_energy.dashboard.contracts import DashboardContractError


def build_model_summary(models: pd.DataFrame, config: DashboardConfig) -> pd.DataFrame:
    selected = models.loc[models["selected_for_production"].astype(str).str.lower().eq("true")].copy()
    rows: list[dict[str, object]] = []
    for side in ("demand", "supply"):
        side_rows = selected.loc[selected["domain"].eq(side)]
        if side_rows.empty:
            raise DashboardContractError(f"Production model missing for {side}")
        model_ids = sorted(side_rows["production_model_id"].astype(str).unique())
        if len(model_ids) != 1:
            raise DashboardContractError(f"Multiple production model IDs for {side}: {model_ids}")
        model_id = model_ids[0]
        if side == "demand":
            active_model = "drift"
            note = "Distributed-electricity production forecast from validated Drift outputs."
        elif model_id == "supply_production_national_reconciled_v2":
            active_model = "national_reconciled_supply"
            note = "Local-generation production forecast from validated National Reconciled Supply (v2) outputs."
        else:
            active_model = "drift"
            note = "Local-generation production forecast from validated Drift V1 outputs."
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
            }
        )
    return pd.DataFrame(rows)
