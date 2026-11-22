from __future__ import annotations

import numpy as np
import pandas as pd

from ecadin_energy.experiments.common.base import (
    BaselineRecursiveAdapter,
    PanelExperimentModel,
    SeriesExperimentModel,
)
from ecadin_energy.experiments.common.models import (
    HoltDampedModel,
    HuberTrendModel,
    RecentWindowDriftModel,
    RecentWindowOLSModel,
    TheilSenTrendModel,
    ThetaModel,
    _prepare_series,
)


class StepInterventionOLSModel:
    """Interrupted Time Series OLS with leakage-free 2021 level-shift dummy."""

    family = "structural_break"
    is_baseline = False

    def __init__(self, break_year: int = 2021) -> None:
        self.break_year = int(break_year)
        self.model_id = "step_intervention_ols"
        self.model_label = f"Step Intervention OLS (I>={self.break_year})"

    def forecast_horizons(
        self,
        history: pd.DataFrame,
        origin_year: int,
        forecast_years: tuple[int, ...],
    ) -> dict[int, float]:
        years, values = _prepare_series(history, origin_year)
        if len(years) == 0:
            return {int(y): float("nan") for y in forecast_years}
        if len(years) < 2 or float(np.ptp(values)) <= 1e-12:
            last_val = float(values[-1])
            return {int(y): last_val for y in forecast_years}

        t0 = float(years[0])
        x = years.astype(float) - t0
        dummy = (years >= self.break_year).astype(float)
        use_dummy = (
            int(origin_year) >= self.break_year
            and bool(np.any(dummy == 1.0))
            and bool(np.any(dummy == 0.0))
            and len(years) >= 3
        )
        if use_dummy:
            design = np.column_stack([np.ones_like(x), x, dummy])
            if np.linalg.matrix_rank(design) == 3:
                coef = np.linalg.lstsq(design, values, rcond=None)[0]
                a, b, d = float(coef[0]), float(coef[1]), float(coef[2])
                return {
                    int(y): float(
                        a
                        + b * (float(y) - t0)
                        + d * (1.0 if int(y) >= self.break_year else 0.0)
                    )
                    for y in forecast_years
                }

        design_lin = np.column_stack([np.ones_like(x), x])
        coef = np.linalg.lstsq(design_lin, values, rcond=None)[0]
        a, b = float(coef[0]), float(coef[1])
        return {
            int(y): float(a + b * (float(y) - t0))
            for y in forecast_years
        }


class StepInterventionDampedModel:
    """FWL step-intervention trend with Ridge slope regularization and damping."""

    family = "structural_break"
    is_baseline = False

    def __init__(
        self,
        break_year: int = 2021,
        lambda_slope: float = 25.0,
        phi: float = 0.85,
    ) -> None:
        self.break_year = int(break_year)
        self.lambda_slope = float(lambda_slope)
        self.phi = float(phi)
        self.model_id = "step_intervention_damped"
        self.model_label = (
            f"Step Intervention Damped (I>={self.break_year}, phi={self.phi:.2f})"
        )

    def forecast_horizons(
        self,
        history: pd.DataFrame,
        origin_year: int,
        forecast_years: tuple[int, ...],
    ) -> dict[int, float]:
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
            y_tilde[pre_mask] = values[pre_mask] - float(np.mean(values[pre_mask]))
            t_tilde[post_mask] = t[post_mask] - float(np.mean(t[post_mask]))
            y_tilde[post_mask] = values[post_mask] - float(np.mean(values[post_mask]))
        else:
            t_tilde = t - float(np.mean(t))
            y_tilde = values - float(np.mean(values))

        s_tt = float(np.sum(t_tilde * t_tilde))
        s_ty = float(np.sum(t_tilde * y_tilde))
        denom = s_tt + self.lambda_slope
        slope = s_ty / denom if denom > 0.0 else 0.0

        results: dict[int, float] = {}
        for y in forecast_years:
            target = int(y)
            steps = target - last_year
            if steps <= 0:
                results[target] = last_val
            else:
                damped_steps = sum(self.phi**j for j in range(1, steps + 1))
                results[target] = float(last_val + slope * damped_steps)
        return results


class PostBreakDriftOrNaiveModel:
    """Regime-aware Drift using post-2021 data when >=2 points exist, else Naive."""

    family = "structural_break"
    is_baseline = False

    def __init__(self, break_year: int = 2021) -> None:
        self.break_year = int(break_year)
        self.model_id = "post_break_drift_or_naive"
        self.model_label = f"Post-Break Drift or Naive (>={self.break_year})"
        self._pre_break_drift = BaselineRecursiveAdapter("drift")

    def forecast_horizons(
        self,
        history: pd.DataFrame,
        origin_year: int,
        forecast_years: tuple[int, ...],
    ) -> dict[int, float]:
        if int(origin_year) < self.break_year:
            return self._pre_break_drift.forecast_horizons(
                history,
                origin_year,
                forecast_years,
            )

        years, values = _prepare_series(history, origin_year)
        if len(years) == 0:
            return {int(y): float("nan") for y in forecast_years}
        last_val = float(values[-1])
        last_year = int(years[-1])

        post_mask = years >= self.break_year
        post_years = years[post_mask]
        post_values = values[post_mask]
        if len(post_years) < 2:
            return {int(y): last_val for y in forecast_years}

        span = int(post_years[-1] - post_years[0])
        slope = (
            (float(post_values[-1]) - float(post_values[0])) / float(span)
            if span > 0
            else 0.0
        )
        return {
            int(y): float(last_val + slope * float(int(y) - last_year))
            for y in forecast_years
        }


class NationalReconciledSupplyModel:
    """Top-down proportional reconciliation of regional forecasts to national forecast."""

    family = "hierarchical_reconciliation"
    is_baseline = False

    def __init__(
        self,
        *,
        base_regional_model: SeriesExperimentModel | None = None,
        national_model: SeriesExperimentModel | None = None,
        national_start_year: int = 2013,
    ) -> None:
        self.base_regional_model = (
            base_regional_model
            if base_regional_model is not None
            else StepInterventionDampedModel()
        )
        self.national_model = (
            national_model
            if national_model is not None
            else BaselineRecursiveAdapter("drift")
        )
        self.national_start_year = int(national_start_year)
        self.model_id = "national_reconciled_supply"
        nat_label = (
            "drift_nat"
            if self.national_model.model_id == "drift"
            else self.national_model.model_id
        )
        self.model_label = (
            f"National Reconciled Supply "
            f"({nat_label} -> {self.base_regional_model.model_id})"
        )

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
        nat_raw = self.national_model.forecast_horizons(
            nat_history,
            origin,
            forecast_years,
        )
        nat_fcst = {
            int(y): max(0.0, float(nat_raw[int(y)]))
            for y in forecast_years
        }

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
                    reconciled[(rid, target)] = float(reg_nonneg[(rid, target)] * scale)
            elif last_total > 0.0:
                scale = nat_target / last_total
                for rid in region_ids:
                    reconciled[(rid, target)] = float(last_observed[rid] * scale)
            else:
                equal_share = nat_target / float(max(1, len(region_ids)))
                for rid in region_ids:
                    reconciled[(rid, target)] = float(equal_share)
        return reconciled


def build_supply_models() -> tuple[
    tuple[SeriesExperimentModel, ...],
    tuple[PanelExperimentModel, ...],
]:
    series_models: tuple[SeriesExperimentModel, ...] = (
        BaselineRecursiveAdapter("naive_lag1"),
        BaselineRecursiveAdapter("drift"),
        BaselineRecursiveAdapter("moving_average_3"),
        BaselineRecursiveAdapter("average_growth_3"),
        StepInterventionOLSModel(),
        StepInterventionDampedModel(),
        PostBreakDriftOrNaiveModel(),
        RecentWindowDriftModel(window=4),
        RecentWindowOLSModel(window=5),
        HoltDampedModel(),
        ThetaModel(),
        TheilSenTrendModel(),
        HuberTrendModel(),
    )
    panel_models: tuple[PanelExperimentModel, ...] = (
        NationalReconciledSupplyModel(),
    )
    return series_models, panel_models
