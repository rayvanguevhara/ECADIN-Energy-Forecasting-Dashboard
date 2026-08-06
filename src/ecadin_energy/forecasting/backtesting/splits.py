from __future__ import annotations

from dataclasses import dataclass

from ecadin_energy.forecasting.configuration import ProductionConfig


@dataclass(frozen=True)
class BacktestSplit:
    protocol: str
    origin_year: int
    target_year: int
    horizon: int


def rolling_one_step_splits(
    target_years: tuple[int, ...],
) -> tuple[BacktestSplit, ...]:
    return tuple(
        BacktestSplit(
            protocol="rolling_one_step",
            origin_year=target_year - 1,
            target_year=target_year,
            horizon=1,
        )
        for target_year in target_years
    )


def recursive_splits(
    origins: tuple[int, ...],
    max_horizon: int,
) -> tuple[BacktestSplit, ...]:
    return tuple(
        BacktestSplit(
            protocol="recursive_multi_step",
            origin_year=origin,
            target_year=origin + horizon,
            horizon=horizon,
        )
        for origin in origins
        for horizon in range(1, max_horizon + 1)
    )


def configured_splits(
    config: ProductionConfig,
) -> tuple[BacktestSplit, ...]:
    return (
        *rolling_one_step_splits(config.one_step_target_years),
        *recursive_splits(
            config.recursive_origins,
            config.recursive_max_horizon,
        ),
    )
