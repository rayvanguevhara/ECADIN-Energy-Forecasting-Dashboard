from __future__ import annotations

import numpy as np
import pandas as pd


def _compare_against_reference(
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
    return compared


def _aggregate_win_rate(
    compared: pd.DataFrame,
    group_columns: list[str],
    *,
    reference_model: str,
) -> pd.DataFrame:
    summary = (
        compared.groupby(
            group_columns,
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


def win_rate_vs_reference(
    predictions: pd.DataFrame,
    *,
    reference_model: str,
) -> pd.DataFrame:
    compared = _compare_against_reference(
        predictions,
        reference_model=reference_model,
    )
    return _aggregate_win_rate(
        compared,
        ["domain", "protocol", "model"],
        reference_model=reference_model,
    )


def win_rate_by_horizon(
    predictions: pd.DataFrame,
    *,
    reference_model: str,
) -> pd.DataFrame:
    """Compute challenger win rates against reference stratified by horizon."""
    compared = _compare_against_reference(
        predictions,
        reference_model=reference_model,
    )
    summary = _aggregate_win_rate(
        compared,
        ["domain", "protocol", "horizon", "model"],
        reference_model=reference_model,
    )
    return summary.sort_values(
        ["domain", "protocol", "horizon", "model"]
    ).reset_index(drop=True)


def win_rate_by_regime(
    predictions: pd.DataFrame,
    *,
    reference_model: str,
    post_regime_start_year: int = 2022,
) -> pd.DataFrame:
    """Compute challenger win rates across pre-2022 and post-2021 regimes."""
    compared = _compare_against_reference(
        predictions,
        reference_model=reference_model,
    )
    slices = [
        ("all_years", pd.Series(True, index=compared.index)),
        ("pre_2022", compared["forecast_year"].lt(post_regime_start_year)),
        ("post_2021", compared["forecast_year"].ge(post_regime_start_year)),
        (
            "post_2021_origins",
            compared["origin_year"].ge(post_regime_start_year - 1)
            & compared["forecast_year"].ge(post_regime_start_year),
        ),
    ]
    frames: list[pd.DataFrame] = []
    for regime, mask in slices:
        subset = compared.loc[mask]
        if subset.empty:
            continue
        summary = _aggregate_win_rate(
            subset,
            ["domain", "protocol", "model"],
            reference_model=reference_model,
        )
        summary.insert(2, "regime", regime)
        summary.insert(3, "forecast_year_min", int(subset["forecast_year"].min()))
        summary.insert(4, "forecast_year_max", int(subset["forecast_year"].max()))
        frames.append(summary)
    if not frames:
        return pd.DataFrame(
            columns=[
                "domain",
                "protocol",
                "regime",
                "forecast_year_min",
                "forecast_year_max",
                "model",
                "comparisons",
                "wins",
                "ties",
                "losses",
                "win_rate_vs_reference",
                "reference_model",
            ]
        )
    return (
        pd.concat(frames, ignore_index=True)
        .sort_values(["domain", "protocol", "regime", "model"])
        .reset_index(drop=True)
    )
