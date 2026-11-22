from __future__ import annotations

import math

import numpy as np
import pandas as pd

from ecadin_energy.forecasting.configuration import SupplyModelParams
from ecadin_energy.forecasting.evaluation.metrics import clip_nonnegative
from ecadin_energy.forecasting.models.drift import DriftModel


def _prepare_series(
    history: pd.DataFrame,
    origin_year: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Filter strictly leak-free history (year <= origin_year) ordered ascending."""
    filtered = (
        history.loc[
            history["year"].le(int(origin_year)),
            ["year", "target_gwh"],
        ]
        .dropna(subset=["year", "target_gwh"])
        .sort_values("year")
    )
    if filtered.empty:
        return np.array([], dtype=int), np.array([], dtype=float)
    return (
        filtered["year"].to_numpy(dtype=int),
        filtered["target_gwh"].to_numpy(dtype=float),
    )


class StepInterventionDampedModel:
    """FWL step-intervention trend with Ridge slope regularization and damping."""

    def __init__(
        self,
        *,
        break_year: int,
        ridge_lambda: float,
        damping_phi: float,
    ) -> None:
        if not (math.isfinite(float(ridge_lambda)) and float(ridge_lambda) > 0.0):
            raise ValueError("ridge_lambda must be positive and finite")
        if not (
            math.isfinite(float(damping_phi)) and 0.0 < float(damping_phi) <= 1.0
        ):
            raise ValueError("damping_phi must lie in (0, 1]")
        self.break_year = int(break_year)
        self.ridge_lambda = float(ridge_lambda)
        self.damping_phi = float(damping_phi)
        self.model_id = "step_intervention_damped"
        self.model_label = (
            f"Step Intervention Damped (I>={self.break_year}, "
            f"phi={self.damping_phi:.2f})"
        )

    def forecast_horizons(
        self,
        history: pd.DataFrame,
        origin_year: int,
        forecast_years: tuple[int, ...],
    ) -> dict[int, float]:
        """Forecast horizons directly with zero leakage beyond origin_year."""
        years, values = _prepare_series(history, origin_year)
        if len(years) == 0:
            return {int(y): float("nan") for y in forecast_years}
        last_val = float(values[-1])
        last_year = int(years[-1])
        if len(years) < 2 or float(np.ptp(values)) <= 1e-12:
            return {int(y): last_val for y in forecast_years}

        t = years.astype(float)
        pre_mask = years < self.break_year
        post_mask = years >= self.break_year

        if (
            int(origin_year) >= self.break_year
            and bool(np.any(pre_mask))
            and bool(np.any(post_mask))
        ):
            t_tilde = np.empty_like(t)
            y_tilde = np.empty_like(values)
            t_tilde[pre_mask] = t[pre_mask] - float(np.mean(t[pre_mask]))
            y_tilde[pre_mask] = values[pre_mask] - float(
                np.mean(values[pre_mask])
            )
            t_tilde[post_mask] = t[post_mask] - float(np.mean(t[post_mask]))
            y_tilde[post_mask] = values[post_mask] - float(
                np.mean(values[post_mask])
            )
        else:
            t_tilde = t - float(np.mean(t))
            y_tilde = values - float(np.mean(values))

        s_tt = float(np.sum(t_tilde * t_tilde))
        s_ty = float(np.sum(t_tilde * y_tilde))
        denom = s_tt + self.ridge_lambda
        slope = s_ty / denom if denom > 0.0 else 0.0

        results: dict[int, float] = {}
        for y in forecast_years:
            target = int(y)
            steps = target - last_year
            if steps <= 0:
                results[target] = last_val
            else:
                damped_steps = sum(
                    self.damping_phi**j for j in range(1, steps + 1)
                )
                results[target] = float(last_val + slope * damped_steps)
        return results


class NationalReconciledSupplyModel:
    """Top-down proportional reconciliation of regional step-damped forecasts to national Drift."""

    def __init__(
        self,
        *,
        break_year: int,
        ridge_lambda: float,
        damping_phi: float,
        national_start_year: int,
        model_id: str = "national_reconciled_supply",
        model_label: str | None = None,
    ) -> None:
        self.break_year = int(break_year)
        self.ridge_lambda = float(ridge_lambda)
        self.damping_phi = float(damping_phi)
        self.national_start_year = int(national_start_year)
        self.base_regional_model = StepInterventionDampedModel(
            break_year=self.break_year,
            ridge_lambda=self.ridge_lambda,
            damping_phi=self.damping_phi,
        )
        self.national_model = DriftModel()
        self.model_id = str(model_id)
        self.model_label = (
            str(model_label)
            if model_label is not None
            else (
                "National Reconciled Supply "
                "(drift_nat -> step_intervention_damped)"
            )
        )

    @classmethod
    def from_params(
        cls,
        params: SupplyModelParams,
        *,
        model_id: str = "national_reconciled_supply",
        model_label: str | None = None,
    ) -> NationalReconciledSupplyModel:
        return cls(
            break_year=params.break_year,
            ridge_lambda=params.ridge_lambda,
            damping_phi=params.damping_phi,
            national_start_year=params.national_start_year,
            model_id=model_id,
            model_label=model_label,
        )

    def _forecast_national_drift(
        self,
        nat_history: pd.DataFrame,
        origin_year: int,
        forecast_years: tuple[int, ...],
    ) -> dict[int, float]:
        ordered = (
            nat_history.loc[
                nat_history["year"].le(int(origin_year)),
                ["year", "target_gwh"],
            ]
            .dropna(subset=["year", "target_gwh"])
            .sort_values("year")
            .reset_index(drop=True)
        )
        if ordered.empty:
            return {int(year): 0.0 for year in forecast_years}

        recursive_history = ordered.copy()
        nat_fcst: dict[int, float] = {}
        for target_year in forecast_years:
            target = int(target_year)
            raw_prediction = float(
                self.national_model.predict_next(recursive_history, target)
            )
            clipped, _ = clip_nonnegative(raw_prediction)
            nat_fcst[target] = (
                max(0.0, float(raw_prediction))
                if np.isfinite(raw_prediction)
                else 0.0
            )
            if pd.notna(clipped):
                recursive_history = pd.concat(
                    [
                        recursive_history,
                        pd.DataFrame(
                            {
                                "year": [target],
                                "target_gwh": [float(clipped)],
                            }
                        ),
                    ],
                    ignore_index=True,
                )
        return nat_fcst

    def forecast_panel(
        self,
        panel_history: pd.DataFrame,
        origin_year: int,
        forecast_years: tuple[int, ...],
        region_ids: tuple[str, ...],
    ) -> dict[tuple[str, int], float]:
        """Forecast all regions from strictly leak-free history and reconcile to national sum."""
        origin = int(origin_year)
        eligible = panel_history.loc[
            panel_history["year"].le(origin)
            & panel_history["training_eligible"]
            & panel_history["training_gwh"].notna()
        ].copy()

        nat_source = eligible.loc[eligible["year"].ge(self.national_start_year)]
        if nat_source.empty:
            nat_source = eligible
        nat_history = (
            nat_source.groupby("year", as_index=False)["training_gwh"]
            .sum()
            .rename(columns={"training_gwh": "target_gwh"})
            .sort_values("year")
            .reset_index(drop=True)
        )
        nat_fcst = self._forecast_national_drift(
            nat_history,
            origin,
            forecast_years,
        )

        reg_nonneg: dict[tuple[str, int], float] = {}
        last_observed: dict[str, float] = {}
        for region_id in region_ids:
            reg_df = (
                eligible.loc[
                    eligible["region_id"].eq(region_id),
                    ["year", "training_gwh"],
                ]
                .rename(columns={"training_gwh": "target_gwh"})
                .sort_values("year")
                .reset_index(drop=True)
            )
            last_observed[region_id] = (
                max(0.0, float(reg_df.iloc[-1]["target_gwh"]))
                if not reg_df.empty
                else 0.0
            )
            raw_map = self.base_regional_model.forecast_horizons(
                reg_df,
                origin,
                forecast_years,
            )
            for y in forecast_years:
                target = int(y)
                val = raw_map[target]
                reg_nonneg[(region_id, target)] = (
                    max(0.0, float(val)) if np.isfinite(val) else 0.0
                )

        last_total = sum(last_observed.values())
        reconciled: dict[tuple[str, int], float] = {}
        for y in forecast_years:
            target = int(y)
            denom = sum(reg_nonneg[(rid, target)] for rid in region_ids)
            nat_target = nat_fcst[target]
            if denom > 0.0:
                scale = nat_target / denom
                for rid in region_ids:
                    reconciled[(rid, target)] = float(
                        reg_nonneg[(rid, target)] * scale
                    )
            elif last_total > 0.0:
                scale = nat_target / last_total
                for rid in region_ids:
                    reconciled[(rid, target)] = float(
                        last_observed[rid] * scale
                    )
            else:
                equal_share = nat_target / float(max(1, len(region_ids)))
                for rid in region_ids:
                    reconciled[(rid, target)] = float(equal_share)
        return reconciled
