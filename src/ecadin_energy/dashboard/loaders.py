from __future__ import annotations

from pathlib import Path

import pandas as pd

from ecadin_energy.dashboard.contracts import DashboardContractError


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"Dashboard input missing: {path}")
    return pd.read_csv(path, low_memory=False)


def load_dashboard_inputs(root: Path) -> dict[str, pd.DataFrame | Path]:
    combined_path = root / "outputs/production/combined/regional_energy_history_forecast.csv"
    model_path = root / "outputs/production/metrics/production_model_summary.csv"
    regions_path = root / "data/reference/regions.csv"
    quality_path = root / "data/processed/master/data_quality_flags.csv"
    contract_path = root / "outputs/production/reports/production_contract_checks.csv"

    combined = _read_csv(combined_path)
    models = _read_csv(model_path)
    regions = _read_csv(regions_path)
    quality = _read_csv(quality_path)
    contracts = _read_csv(contract_path)

    if not contracts["passed"].astype(str).str.lower().eq("true").all():
        raise DashboardContractError("Forecast production contracts are not all passed")
    return {
        "combined": combined,
        "models": models,
        "regions": regions,
        "quality_flags": quality,
        "production_contracts": contracts,
        "combined_path": combined_path,
        "model_path": model_path,
        "regions_path": regions_path,
        "quality_path": quality_path,
        "contract_path": contract_path,
    }
