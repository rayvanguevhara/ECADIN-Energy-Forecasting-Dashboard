from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ecadin_energy.config import PATHS
from ecadin_energy.forecasting.exceptions import ConfigurationError


@dataclass(frozen=True)
class MissingDataPolicy:
    interpolate_years: tuple[int, ...]
    exclude_pre_year_regions: tuple[str, ...]
    exclude_before_year: int
    allow_silent_fill: bool


@dataclass(frozen=True)
class DomainConfig:
    target_column: str
    dataset_id: str
    production_model_id: str
    model_label: str
    output_value_column: str


@dataclass(frozen=True)
class ProductionConfig:
    schema_version: str
    history_start_year: int
    history_end_year: int
    forecast_start_year: int
    forecast_end_year: int
    expected_regions: int
    baseline_models: tuple[str, ...]
    reference_baseline: str
    one_step_target_years: tuple[int, ...]
    recursive_origins: tuple[int, ...]
    recursive_max_horizon: int
    missing_data: MissingDataPolicy
    demand: DomainConfig
    supply: DomainConfig
    accounting_difference_label: str
    accounting_disclaimer: str

    @property
    def forecast_years(self) -> tuple[int, ...]:
        return tuple(range(self.forecast_start_year, self.forecast_end_year + 1))

    @property
    def historical_years(self) -> tuple[int, ...]:
        return tuple(range(self.history_start_year, self.history_end_year + 1))


def _require(mapping: dict[str, Any], key: str, context: str) -> Any:
    if key not in mapping:
        raise ConfigurationError(f"Missing configuration key: {context}.{key}")
    return mapping[key]


def _domain(mapping: dict[str, Any], name: str) -> DomainConfig:
    block = _require(mapping, name, "root")
    return DomainConfig(
        target_column=str(_require(block, "target_column", name)),
        dataset_id=str(_require(block, "dataset_id", name)),
        production_model_id=str(
            _require(block, "production_model_id", name)
        ),
        model_label=str(_require(block, "model_label", name)),
        output_value_column=str(
            _require(block, "output_value_column", name)
        ),
    )


def load_production_config(
    path: str | Path | None = None,
    *,
    project_root: str | Path | None = None,
) -> ProductionConfig:
    root = Path(project_root).resolve() if project_root else PATHS.root
    config_path = (
        Path(path)
        if path is not None
        else root / "configs/forecasting/production.json"
    )
    if not config_path.is_absolute():
        config_path = root / config_path
    if not config_path.is_file():
        raise FileNotFoundError(f"Forecasting config not found: {config_path}")

    raw = json.loads(config_path.read_text(encoding="utf-8"))
    missing = _require(raw, "missing_data", "root")
    config = ProductionConfig(
        schema_version=str(_require(raw, "schema_version", "root")),
        history_start_year=int(
            _require(raw, "history_start_year", "root")
        ),
        history_end_year=int(_require(raw, "history_end_year", "root")),
        forecast_start_year=int(
            _require(raw, "forecast_start_year", "root")
        ),
        forecast_end_year=int(_require(raw, "forecast_end_year", "root")),
        expected_regions=int(_require(raw, "expected_regions", "root")),
        baseline_models=tuple(
            str(value) for value in _require(raw, "baseline_models", "root")
        ),
        reference_baseline=str(
            _require(raw, "reference_baseline", "root")
        ),
        one_step_target_years=tuple(
            int(value)
            for value in _require(raw, "one_step_target_years", "root")
        ),
        recursive_origins=tuple(
            int(value)
            for value in _require(raw, "recursive_origins", "root")
        ),
        recursive_max_horizon=int(
            _require(raw, "recursive_max_horizon", "root")
        ),
        missing_data=MissingDataPolicy(
            interpolate_years=tuple(
                int(value)
                for value in _require(
                    missing,
                    "interpolate_years",
                    "missing_data",
                )
            ),
            exclude_pre_year_regions=tuple(
                str(value)
                for value in _require(
                    missing,
                    "exclude_pre_year_regions",
                    "missing_data",
                )
            ),
            exclude_before_year=int(
                _require(
                    missing,
                    "exclude_before_year",
                    "missing_data",
                )
            ),
            allow_silent_fill=bool(
                _require(
                    missing,
                    "allow_silent_fill",
                    "missing_data",
                )
            ),
        ),
        demand=_domain(raw, "demand"),
        supply=_domain(raw, "supply"),
        accounting_difference_label=str(
            _require(raw, "accounting_difference_label", "root")
        ),
        accounting_disclaimer=str(
            _require(raw, "accounting_disclaimer", "root")
        ),
    )
    validate_production_config(config)
    return config


def validate_interpolation_origin_guard(
    interpolate_years: Iterable[int],
    origins: Iterable[int],
) -> str | None:
    """Verify backtest origins strictly follow interpolated years and their neighbors."""
    interp = [int(year) for year in interpolate_years]
    origin_list = [int(origin) for origin in origins]
    if not interp or not origin_list:
        return None
    max_interp = max(interp)
    min_origin = min(origin_list)
    if min_origin <= max_interp + 1:
        return (
            f"backtest origin {min_origin} risks interpolation leakage from "
            f"year {max_interp} (requires min(origins) > {max_interp + 1})"
        )
    return None


def validate_production_config(config: ProductionConfig) -> None:
    failures: list[str] = []
    if config.history_start_year >= config.history_end_year:
        failures.append("history_start_year must be before history_end_year")
    if config.forecast_start_year != config.history_end_year + 1:
        failures.append(
            "forecast_start_year must immediately follow history_end_year"
        )
    if config.forecast_start_year > config.forecast_end_year:
        failures.append("forecast_start_year must not exceed forecast_end_year")
    if config.expected_regions <= 0:
        failures.append("expected_regions must be positive")
    if config.reference_baseline not in config.baseline_models:
        failures.append("reference_baseline must be in baseline_models")
    if config.recursive_max_horizon <= 0:
        failures.append("recursive_max_horizon must be positive")
    if config.missing_data.allow_silent_fill:
        failures.append("allow_silent_fill must remain false")
    all_origins = [
        *(int(year) - 1 for year in config.one_step_target_years),
        *(int(origin) for origin in config.recursive_origins),
    ]
    guard_error = validate_interpolation_origin_guard(
        config.missing_data.interpolate_years,
        all_origins,
    )
    if guard_error is not None:
        failures.append(guard_error)
    if failures:
        raise ConfigurationError(" | ".join(failures))
