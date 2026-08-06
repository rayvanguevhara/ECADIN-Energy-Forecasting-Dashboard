from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SeriesSpec:
    domain: str
    dataset_id: str
    target_column: str
    model_id: str
    model_label: str
    output_value_column: str


@dataclass(frozen=True)
class BacktestSpec:
    one_step_target_years: tuple[int, ...]
    recursive_origins: tuple[int, ...]
    recursive_max_horizon: int


@dataclass(frozen=True)
class ForecastRecord:
    domain: str
    model_version: str
    protocol: str
    model: str
    reference_baseline: str
    region_id: str
    region_name: str
    origin_year: int
    forecast_year: int
    horizon: int
    actual_gwh: float
    prediction_raw_gwh: float
    prediction_gwh: float
    error_gwh: float
    absolute_error_gwh: float
    squared_error_gwh2: float
    ape_percent: float | None
    smape_percent: float
    mase_scale_gwh: float | None
    mase: float | None
    training_observation_count: int
    training_first_year: int | None
    training_last_year: int | None
    was_clipped_nonnegative: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            field: getattr(self, field)
            for field in self.__dataclass_fields__
        }
