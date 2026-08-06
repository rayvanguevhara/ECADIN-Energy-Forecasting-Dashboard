from __future__ import annotations

import pandas as pd

from ecadin_energy.forecasting.models.drift import drift_slope


def training_history(region_frame: pd.DataFrame) -> pd.DataFrame:
    history = region_frame.loc[
        region_frame["training_eligible"]
        & region_frame["training_gwh"].notna(),
        ["year", "training_gwh"],
    ].copy()
    return (
        history.rename(columns={"training_gwh": "target_gwh"})
        .sort_values("year")
        .reset_index(drop=True)
    )


def history_summary(panel: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for _, group in panel.groupby("region_id", sort=False):
        history = training_history(group)
        if len(history) < 2:
            raise ValueError(
                f"Insufficient production history: "
                f"{group.iloc[0]['region_id']}"
            )
        first = history.iloc[0]
        last = history.iloc[-1]
        rows.append(
            {
                "region_id": str(group.iloc[0]["region_id"]),
                "region_name": str(group.iloc[0]["region_name"]),
                "modeling_order": int(group.iloc[0]["modeling_order"]),
                "history_observation_count": int(len(history)),
                "history_first_year": int(first["year"]),
                "history_last_year": int(last["year"]),
                "history_first_gwh": float(first["target_gwh"]),
                "history_last_gwh": float(last["target_gwh"]),
                "drift_slope_gwh_per_year": float(
                    drift_slope(history)
                ),
                "interpolated_history_count": int(
                    group.loc[
                        group["training_eligible"],
                        "is_interpolated_target",
                    ].sum()
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(
        "modeling_order"
    ).reset_index(drop=True)
