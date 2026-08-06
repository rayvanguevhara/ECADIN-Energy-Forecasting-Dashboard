from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

from ecadin_energy.forecasting.exceptions import ContractError


def _validate_history(history: pd.DataFrame, target_year: int) -> pd.DataFrame:
    required = {"year", "target_gwh"}
    missing = sorted(required - set(history.columns))
    if missing:
        raise ContractError(f"Lag history is missing columns: {missing}")
    frame = history[["year", "target_gwh"]].copy()
    frame["year"] = pd.to_numeric(frame["year"], errors="raise").astype(int)
    frame["target_gwh"] = pd.to_numeric(
        frame["target_gwh"],
        errors="coerce",
    )
    frame = frame.dropna(subset=["target_gwh"]).sort_values("year")
    if frame["year"].duplicated().any():
        raise ContractError("Lag history contains duplicate years")
    if not frame.empty and int(frame["year"].max()) >= int(target_year):
        raise ContractError(
            "Leakage detected: lag history reaches the target year"
        )
    return frame.reset_index(drop=True)


def build_lag_features(
    history: pd.DataFrame,
    *,
    target_year: int,
    lags: Iterable[int] = (1, 2, 3),
    rolling_windows: Iterable[int] = (3,),
) -> dict[str, float]:
    frame = _validate_history(history, target_year)
    by_year = frame.set_index("year")["target_gwh"].to_dict()
    features: dict[str, float] = {}

    for lag in lags:
        lag = int(lag)
        if lag <= 0:
            raise ValueError("Lag values must be positive")
        value = by_year.get(int(target_year) - lag)
        features[f"lag_{lag}_gwh"] = (
            float(value) if value is not None else np.nan
        )

    for window in rolling_windows:
        window = int(window)
        if window <= 0:
            raise ValueError("Rolling windows must be positive")
        values = frame.loc[
            frame["year"].between(
                int(target_year) - window,
                int(target_year) - 1,
            ),
            "target_gwh",
        ]
        features[f"rolling_mean_{window}_gwh"] = (
            float(values.mean()) if len(values) == window else np.nan
        )

    features["feature_origin_year"] = (
        int(frame["year"].max()) if not frame.empty else np.nan
    )
    features["target_year"] = int(target_year)
    return features


def build_supervised_lag_frame(
    series: pd.DataFrame,
    *,
    lags: Iterable[int] = (1, 2, 3),
    rolling_windows: Iterable[int] = (3,),
) -> pd.DataFrame:
    required = {"year", "target_gwh"}
    missing = sorted(required - set(series.columns))
    if missing:
        raise ContractError(f"Series is missing columns: {missing}")
    frame = series[["year", "target_gwh"]].copy()
    frame["year"] = pd.to_numeric(frame["year"], errors="raise").astype(int)
    frame["target_gwh"] = pd.to_numeric(
        frame["target_gwh"],
        errors="coerce",
    )
    frame = frame.sort_values("year").reset_index(drop=True)

    rows: list[dict[str, float]] = []
    for row in frame.itertuples(index=False):
        if pd.isna(row.target_gwh):
            continue
        history = frame.loc[
            frame["year"] < int(row.year),
            ["year", "target_gwh"],
        ]
        features = build_lag_features(
            history,
            target_year=int(row.year),
            lags=lags,
            rolling_windows=rolling_windows,
        )
        rows.append(
            {
                **features,
                "target_gwh": float(row.target_gwh),
            }
        )
    return pd.DataFrame(rows)
