from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ecadin_energy.experiments.common.base import (
    BaselineRecursiveAdapter,
    PanelExperimentModel,
    SeriesExperimentModel,
)
from ecadin_energy.experiments.common.models import (
    DampedDriftModel,
    HoltDampedModel,
    HuberTrendModel,
    OLSLinearTrendModel,
    RecentWindowOLSModel,
    TheilSenTrendModel,
    ThetaModel,
)
from ecadin_energy.forecasting.evaluation.metrics import clip_nonnegative
from ecadin_energy.forecasting.features.lags import (
    build_lag_features,
    build_supervised_lag_frame,
)


class RidgeLagPanelModel:
    """Strictly leakage-free pooled autoregressive Ridge model over lag features."""

    model_id = "ridge_lag_panel"
    model_label = "Ridge Lag Panel (Autoregressive)"
    family = "panel_ml"
    is_baseline = False

    def __init__(self) -> None:
        self._alphas = np.logspace(-1, 4, 25)

    def _extract_feature_vector(
        self,
        lag_1: float,
        lag_2: float,
        lag_3: float,
        rm3: float,
    ) -> list[float]:
        return [
            lag_1 / rm3,
            lag_2 / rm3,
            lag_3 / rm3,
            (lag_1 - lag_3) / (2.0 * rm3),
        ]

    def forecast_panel(
        self,
        panel_history: pd.DataFrame,
        origin_year: int,
        forecast_years: tuple[int, ...],
        region_ids: tuple[str, ...],
    ) -> dict[tuple[str, int], float]:
        origin = int(origin_year)
        eligible = panel_history.loc[
            panel_history["year"].le(origin)
            & panel_history["training_eligible"]
            & panel_history["training_gwh"].notna()
        ].copy()

        x_rows: list[list[float]] = []
        y_rows: list[float] = []
        histories_by_region: dict[str, pd.DataFrame] = {}

        for region_id in region_ids:
            reg_hist = (
                eligible.loc[
                    eligible["region_id"].eq(region_id),
                    ["year", "training_gwh"],
                ]
                .rename(columns={"training_gwh": "target_gwh"})
                .sort_values("year")
                .reset_index(drop=True)
            )
            histories_by_region[region_id] = reg_hist
            if len(reg_hist) < 4:
                continue
            sup = build_supervised_lag_frame(
                reg_hist,
                lags=(1, 2, 3),
                rolling_windows=(3,),
            )
            if sup.empty:
                continue
            if int(sup["target_year"].max()) > origin:
                raise AssertionError(
                    f"Leakage detected in RidgeLagPanelModel: max target_year > {origin}"
                )
            valid = sup.dropna(
                subset=[
                    "lag_1_gwh",
                    "lag_2_gwh",
                    "lag_3_gwh",
                    "rolling_mean_3_gwh",
                    "target_gwh",
                ]
            )
            valid = valid.loc[valid["rolling_mean_3_gwh"] > 0.0]
            for row in valid.itertuples(index=False):
                rm3 = float(row.rolling_mean_3_gwh)
                x_rows.append(
                    self._extract_feature_vector(
                        float(row.lag_1_gwh),
                        float(row.lag_2_gwh),
                        float(row.lag_3_gwh),
                        rm3,
                    )
                )
                y_rows.append(float(row.target_gwh) / rm3)

        model_fitted = False
        pipe: Pipeline | None = None
        if len(x_rows) >= 5:
            x_mat = np.asarray(x_rows, dtype=float)
            y_vec = np.asarray(y_rows, dtype=float)
            pipe = Pipeline(
                [
                    ("scaler", StandardScaler()),
                    ("ridge", RidgeCV(alphas=self._alphas)),
                ]
            )
            pipe.fit(x_mat, y_vec)
            model_fitted = True

        predictions: dict[tuple[str, int], float] = {}
        for region_id in region_ids:
            rec_hist = histories_by_region[region_id].copy()
            last_val = (
                float(rec_hist.iloc[-1]["target_gwh"])
                if not rec_hist.empty
                else float("nan")
            )
            for target_year in forecast_years:
                target = int(target_year)
                raw = last_val
                if model_fitted and pipe is not None and not rec_hist.empty:
                    feats = build_lag_features(
                        rec_hist,
                        target_year=target,
                        lags=(1, 2, 3),
                        rolling_windows=(3,),
                    )
                    lag_1 = feats["lag_1_gwh"]
                    lag_2 = feats["lag_2_gwh"]
                    lag_3 = feats["lag_3_gwh"]
                    rm3 = feats["rolling_mean_3_gwh"]
                    if (
                        np.isfinite(lag_1)
                        and np.isfinite(lag_2)
                        and np.isfinite(lag_3)
                        and np.isfinite(rm3)
                        and rm3 > 0.0
                    ):
                        x_row = np.asarray(
                            [self._extract_feature_vector(lag_1, lag_2, lag_3, rm3)],
                            dtype=float,
                        )
                        raw = float(pipe.predict(x_row)[0] * rm3)
                    elif not rec_hist.empty:
                        raw = float(rec_hist.iloc[-1]["target_gwh"])

                predictions[(region_id, target)] = raw
                clipped, _ = clip_nonnegative(raw)
                if pd.notna(clipped):
                    rec_hist = pd.concat(
                        [
                            rec_hist,
                            pd.DataFrame(
                                {
                                    "year": [target],
                                    "target_gwh": [float(clipped)],
                                }
                            ),
                        ],
                        ignore_index=True,
                    )
        return predictions


def build_demand_models() -> tuple[
    tuple[SeriesExperimentModel, ...],
    tuple[PanelExperimentModel, ...],
]:
    series_models: tuple[SeriesExperimentModel, ...] = (
        BaselineRecursiveAdapter("naive_lag1"),
        BaselineRecursiveAdapter("drift"),
        BaselineRecursiveAdapter("moving_average_3"),
        BaselineRecursiveAdapter("average_growth_3"),
        OLSLinearTrendModel(),
        TheilSenTrendModel(),
        HuberTrendModel(),
        HoltDampedModel(),
        ThetaModel(),
        RecentWindowOLSModel(window=5),
        DampedDriftModel(phi=0.88),
    )
    panel_models: tuple[PanelExperimentModel, ...] = (
        RidgeLagPanelModel(),
    )
    return series_models, panel_models
