from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import theilslopes
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import HuberRegressor


def _prepare_series(
    history: pd.DataFrame,
    origin_year: int,
) -> tuple[np.ndarray, np.ndarray]:
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


def _ols_params(years: np.ndarray, values: np.ndarray) -> tuple[float, float, float]:
    t = years.astype(float)
    t_mean = float(np.mean(t))
    u = t - t_mean
    denom = float(np.sum(u * u))
    y_mean = float(np.mean(values))
    if denom <= 0.0:
        return y_mean, 0.0, t_mean
    slope = float(np.sum(u * (values - y_mean)) / denom)
    return y_mean, slope, t_mean


class OLSLinearTrendModel:
    """Full-history Ordinary Least Squares linear trend model."""

    model_id = "ols_linear_trend"
    model_label = "OLS Linear Trend"
    family = "trend"
    is_baseline = False

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

        y_mean, slope, t_mean = _ols_params(years, values)
        return {
            int(y): float(y_mean + slope * (float(y) - t_mean))
            for y in forecast_years
        }


class RecentWindowDriftModel:
    """Linear drift computed on the most recent window of observations."""

    family = "regime_window"
    is_baseline = False

    def __init__(self, window: int = 4) -> None:
        self.window = int(window)
        self.model_id = f"recent_window_drift_{self.window}"
        self.model_label = f"Recent Window Drift ({self.window}y)"

    def forecast_horizons(
        self,
        history: pd.DataFrame,
        origin_year: int,
        forecast_years: tuple[int, ...],
    ) -> dict[int, float]:
        years, values = _prepare_series(history, origin_year)
        if len(years) == 0:
            return {int(y): float("nan") for y in forecast_years}
        if len(years) >= self.window:
            years = years[-self.window :]
            values = values[-self.window :]
        last_val = float(values[-1])
        last_year = int(years[-1])
        if len(years) < 2 or float(np.ptp(values)) <= 1e-12:
            return {int(y): last_val for y in forecast_years}

        span = int(years[-1] - years[0])
        slope = (last_val - float(values[0])) / float(span) if span > 0 else 0.0
        return {
            int(y): float(last_val + slope * float(int(y) - last_year))
            for y in forecast_years
        }


class RecentWindowOLSModel:
    """OLS linear trend fitted on the most recent window of observations."""

    family = "regime_window"
    is_baseline = False

    def __init__(self, window: int = 5) -> None:
        self.window = int(window)
        self.model_id = f"recent_window_ols_{self.window}"
        self.model_label = f"Recent Window OLS ({self.window}y)"

    def forecast_horizons(
        self,
        history: pd.DataFrame,
        origin_year: int,
        forecast_years: tuple[int, ...],
    ) -> dict[int, float]:
        years, values = _prepare_series(history, origin_year)
        if len(years) == 0:
            return {int(y): float("nan") for y in forecast_years}
        if len(years) >= self.window:
            years = years[-self.window :]
            values = values[-self.window :]
        if len(years) < 2 or float(np.ptp(values)) <= 1e-12:
            last_val = float(values[-1])
            return {int(y): last_val for y in forecast_years}

        y_mean, slope, t_mean = _ols_params(years, values)
        return {
            int(y): float(y_mean + slope * (float(y) - t_mean))
            for y in forecast_years
        }


class DampedDriftModel:
    """Endpoint drift model with geometric horizon damping factor phi."""

    family = "damped_trend"
    is_baseline = False

    def __init__(self, phi: float = 0.88) -> None:
        self.phi = float(phi)
        self.model_id = "damped_drift"
        self.model_label = f"Damped Drift (phi={self.phi:.2f})"

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

        span = int(years[-1] - years[0])
        slope = (last_val - float(values[0])) / float(span) if span > 0 else 0.0
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


class TheilSenTrendModel:
    """Nonparametric median-slope (Theil-Sen) linear trend model."""

    model_id = "theil_sen_trend"
    model_label = "Theil-Sen Robust Trend"
    family = "robust_trend"
    is_baseline = False

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

        res = theilslopes(values, years.astype(float))
        slope = float(res.slope)
        intercept = float(res.intercept)
        if not (np.isfinite(slope) and np.isfinite(intercept)):
            y_mean, ols_slope, t_mean = _ols_params(years, values)
            return {
                int(y): float(y_mean + ols_slope * (float(y) - t_mean))
                for y in forecast_years
            }
        return {
            int(y): float(intercept + slope * float(y))
            for y in forecast_years
        }


class HuberTrendModel:
    """M-estimator (Huber) robust linear trend model."""

    family = "robust_trend"
    is_baseline = False

    def __init__(self, epsilon: float = 1.35) -> None:
        self.epsilon = float(epsilon)
        self.model_id = "huber_trend"
        self.model_label = f"Huber Robust Trend (eps={self.epsilon:.2f})"
        self._fallback = TheilSenTrendModel()

    def forecast_horizons(
        self,
        history: pd.DataFrame,
        origin_year: int,
        forecast_years: tuple[int, ...],
    ) -> dict[int, float]:
        years, values = _prepare_series(history, origin_year)
        if len(years) == 0:
            return {int(y): float("nan") for y in forecast_years}
        if len(years) < 3 or float(np.ptp(values)) <= 1e-12:
            if len(years) < 2 or float(np.ptp(values)) <= 1e-12:
                last_val = float(values[-1])
                return {int(y): last_val for y in forecast_years}
            y_mean, slope, t_mean = _ols_params(years, values)
            return {
                int(y): float(y_mean + slope * (float(y) - t_mean))
                for y in forecast_years
            }

        t = years.astype(float)
        t_mean = float(np.mean(t))
        u = (t - t_mean).reshape(-1, 1)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", ConvergenceWarning)
                reg = HuberRegressor(
                    epsilon=self.epsilon,
                    alpha=0.0,
                    max_iter=500,
                )
                reg.fit(u, values)
            intercept = float(reg.intercept_)
            slope = float(reg.coef_[0])
            if not (np.isfinite(intercept) and np.isfinite(slope)):
                raise ValueError("Non-finite Huber parameters")
            return {
                int(y): float(intercept + slope * (float(y) - t_mean))
                for y in forecast_years
            }
        except Exception:
            return self._fallback.forecast_horizons(history, origin_year, forecast_years)


class HoltDampedModel:
    """Holt's Damped Trend state-space model ETS(A,Ad,N) fitted via SSE."""

    model_id = "holt_damped"
    model_label = "Holt Damped Trend ETS(A,Ad,N)"
    family = "exponential_smoothing"
    is_baseline = False

    _ALPHA_GRID = (0.15, 0.35, 0.55, 0.75, 0.90)
    _BETA_RATIO_GRID = (0.05, 0.25, 0.55, 0.85)
    _PHI_GRID = (0.80, 0.86, 0.92, 0.97)
    _BOUNDS = ((0.05, 0.99), (0.001, 0.99), (0.80, 0.98))

    def _initial_state(
        self,
        years: np.ndarray,
        values: np.ndarray,
    ) -> tuple[float, float]:
        l0 = float(values[0])
        limit = min(4, len(years))
        consecutive_diffs = [
            float(values[i + 1] - values[i])
            for i in range(limit - 1)
            if int(years[i + 1] - years[i]) == 1
        ]
        if consecutive_diffs:
            b0 = float(np.median(consecutive_diffs))
        else:
            span = int(years[1] - years[0])
            b0 = float(values[1] - values[0]) / float(span) if span > 0 else 0.0
        return l0, b0

    def _run_filter(
        self,
        obs_by_year: dict[int, float],
        t_start: int,
        t_end: int,
        l0: float,
        b0: float,
        alpha: float,
        beta_ratio: float,
        phi: float,
    ) -> tuple[float, float, float]:
        level = l0
        slope = b0
        beta = beta_ratio * alpha
        sse = 0.0
        for year in range(t_start + 1, t_end + 1):
            y_hat = level + phi * slope
            obs = obs_by_year.get(year)
            if obs is not None:
                err = obs - y_hat
                sse += err * err
                level = y_hat + alpha * err
                slope = phi * slope + beta * err
            else:
                level = y_hat
                slope = phi * slope
        return sse, level, slope

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
        if len(years) < 3 or float(np.ptp(values)) <= 1e-12:
            if len(years) == 2 and float(np.ptp(values)) > 1e-12:
                span = int(years[1] - years[0])
                slope = (last_val - float(values[0])) / float(span) if span > 0 else 0.0
                return {
                    int(y): float(last_val + slope * float(int(y) - last_year))
                    for y in forecast_years
                }
            return {int(y): last_val for y in forecast_years}

        t_start = int(years[0])
        obs_by_year = {int(yr): float(val) for yr, val in zip(years, values)}
        l0, b0 = self._initial_state(years, values)

        best_params = (0.55, 0.25, 0.90)
        best_sse = float("inf")
        for alpha in self._ALPHA_GRID:
            for beta_ratio in self._BETA_RATIO_GRID:
                for phi in self._PHI_GRID:
                    sse, _, _ = self._run_filter(
                        obs_by_year, t_start, last_year, l0, b0, alpha, beta_ratio, phi
                    )
                    if sse < best_sse:
                        best_sse = sse
                        best_params = (alpha, beta_ratio, phi)

        def objective(theta: np.ndarray) -> float:
            sse, _, _ = self._run_filter(
                obs_by_year,
                t_start,
                last_year,
                l0,
                b0,
                float(theta[0]),
                float(theta[1]),
                float(theta[2]),
            )
            return sse

        res = minimize(
            objective,
            x0=np.array(best_params, dtype=float),
            method="L-BFGS-B",
            bounds=self._BOUNDS,
        )
        opt_alpha, opt_beta_ratio, opt_phi = (
            (float(res.x[0]), float(res.x[1]), float(res.x[2]))
            if np.all(np.isfinite(res.x)) and res.fun <= best_sse + 1e-9
            else best_params
        )
        _, level_t, slope_t = self._run_filter(
            obs_by_year,
            t_start,
            last_year,
            l0,
            b0,
            opt_alpha,
            opt_beta_ratio,
            opt_phi,
        )

        results: dict[int, float] = {}
        for y in forecast_years:
            target = int(y)
            steps = target - last_year
            if steps <= 0:
                results[target] = float(level_t)
            else:
                damped_steps = sum(opt_phi**j for j in range(1, steps + 1))
                results[target] = float(level_t + slope_t * damped_steps)
        return results


class ThetaModel:
    """Standard Theta Method combining Theta=0 (OLS) and SES on Theta=2."""

    model_id = "theta"
    model_label = "Standard Theta Method"
    family = "theta"
    is_baseline = False

    _ALPHA_GRID = (0.10, 0.25, 0.45, 0.65, 0.85, 0.95)

    def _ses_sse(
        self,
        z2_by_year: dict[int, float],
        t_start: int,
        t_end: int,
        l0: float,
        alpha: float,
    ) -> tuple[float, float]:
        level = l0
        sse = 0.0
        for year in range(t_start, t_end + 1):
            obs = z2_by_year.get(year)
            if obs is not None:
                err = obs - level
                sse += err * err
                level = level + alpha * err
        return sse, level

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
        if len(years) < 3 or float(np.ptp(values)) <= 1e-12:
            if len(years) == 2 and float(np.ptp(values)) > 1e-12:
                span = int(years[1] - years[0])
                slope = (last_val - float(values[0])) / float(span) if span > 0 else 0.0
                return {
                    int(y): float(last_val + slope * float(int(y) - last_year))
                    for y in forecast_years
                }
            return {int(y): last_val for y in forecast_years}

        y_mean, b_ols, t_mean = _ols_params(years, values)
        z0 = y_mean + b_ols * (years.astype(float) - t_mean)
        z2 = 2.0 * values - z0
        t_start = int(years[0])
        z2_by_year = {int(yr): float(val) for yr, val in zip(years, z2)}
        init_l0 = float(z2[0])

        best_alpha = 0.50
        best_sse = float("inf")
        for alpha in self._ALPHA_GRID:
            sse, _ = self._ses_sse(z2_by_year, t_start, last_year, init_l0, alpha)
            if sse < best_sse:
                best_sse = sse
                best_alpha = alpha

        def objective(theta: np.ndarray) -> float:
            sse, _ = self._ses_sse(
                z2_by_year, t_start, last_year, float(theta[0]), float(theta[1])
            )
            return sse

        res = minimize(
            objective,
            x0=np.array([init_l0, best_alpha], dtype=float),
            method="L-BFGS-B",
            bounds=((None, None), (0.05, 0.99)),
        )
        opt_l0, opt_alpha = (
            (float(res.x[0]), float(res.x[1]))
            if np.all(np.isfinite(res.x)) and res.fun <= best_sse + 1e-9
            else (init_l0, best_alpha)
        )
        _, level_t = self._ses_sse(z2_by_year, t_start, last_year, opt_l0, opt_alpha)

        return {
            int(y): float(
                0.5 * (y_mean + b_ols * (float(y) - t_mean)) + 0.5 * level_t
            )
            for y in forecast_years
        }
