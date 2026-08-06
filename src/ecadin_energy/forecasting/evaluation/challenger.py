from __future__ import annotations

import numpy as np
import pandas as pd


def win_rate_vs_reference(
    predictions: pd.DataFrame,
    *,
    reference_model: str,
) -> pd.DataFrame:
    key_columns = [
        "domain",
        "protocol",
        "region_id",
        "origin_year",
        "forecast_year",
        "horizon",
    ]
    reference = predictions.loc[
        predictions["model"].eq(reference_model),
        key_columns + ["absolute_error_gwh"],
    ].rename(
        columns={
            "absolute_error_gwh": "reference_absolute_error_gwh"
        }
    )
    compared = predictions.merge(
        reference,
        on=key_columns,
        how="left",
        validate="many_to_one",
    )
    tolerance = 1e-12
    compared["win_score"] = np.select(
        [
            compared["absolute_error_gwh"]
            < compared["reference_absolute_error_gwh"] - tolerance,
            np.isclose(
                compared["absolute_error_gwh"],
                compared["reference_absolute_error_gwh"],
                rtol=1e-12,
                atol=tolerance,
            ),
        ],
        [1.0, 0.5],
        default=0.0,
    )
    summary = (
        compared.groupby(
            ["domain", "protocol", "model"],
            as_index=False,
        )
        .agg(
            comparisons=("win_score", "size"),
            wins=("win_score", lambda x: int((x == 1.0).sum())),
            ties=("win_score", lambda x: int((x == 0.5).sum())),
            losses=("win_score", lambda x: int((x == 0.0).sum())),
            win_rate_vs_reference=("win_score", "mean"),
        )
    )
    summary["reference_model"] = reference_model
    return summary
