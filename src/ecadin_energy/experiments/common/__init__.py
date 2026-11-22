from __future__ import annotations

from ecadin_energy.experiments.common.base import (
    BaselineRecursiveAdapter,
    PanelExperimentModel,
    SeriesExperimentModel,
)
from ecadin_energy.experiments.common.evaluator import (
    DEMAND_KEY_PROVINCES,
    EXTENDED_ORIGIN_HORIZONS,
    SUPPLY_KEY_PROVINCES,
    ModelMetadata,
    build_demand_scenario_table,
    build_horizon_table,
    build_metrics_summary_table,
    build_sanity_check_tables,
    build_supply_regime_table,
    collect_model_metadata,
    run_domain_backtests,
    run_domain_projections_2025_2030,
    verify_production_baseline_parity,
    verify_zero_leakage,
)
from ecadin_energy.experiments.common.models import (
    DampedDriftModel,
    HoltDampedModel,
    HuberTrendModel,
    OLSLinearTrendModel,
    RecentWindowDriftModel,
    RecentWindowOLSModel,
    TheilSenTrendModel,
    ThetaModel,
)
from ecadin_energy.experiments.common.reporting import generate_phase2_report

__all__ = [
    "BaselineRecursiveAdapter",
    "DEMAND_KEY_PROVINCES",
    "DampedDriftModel",
    "EXTENDED_ORIGIN_HORIZONS",
    "HoltDampedModel",
    "HuberTrendModel",
    "ModelMetadata",
    "OLSLinearTrendModel",
    "PanelExperimentModel",
    "RecentWindowDriftModel",
    "RecentWindowOLSModel",
    "SUPPLY_KEY_PROVINCES",
    "SeriesExperimentModel",
    "TheilSenTrendModel",
    "ThetaModel",
    "build_demand_scenario_table",
    "build_horizon_table",
    "build_metrics_summary_table",
    "build_sanity_check_tables",
    "build_supply_regime_table",
    "collect_model_metadata",
    "generate_phase2_report",
    "run_domain_backtests",
    "run_domain_projections_2025_2030",
    "verify_production_baseline_parity",
    "verify_zero_leakage",
]
