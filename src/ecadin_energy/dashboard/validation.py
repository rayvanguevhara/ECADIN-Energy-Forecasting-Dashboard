from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ecadin_energy.config import PATHS
from ecadin_energy.dashboard.configuration import load_dashboard_config
from ecadin_energy.dashboard.contracts import DashboardContractError
from ecadin_energy.dashboard.region_detail import classify_accounting_difference
from ecadin_energy.dashboard.serializers import sha256_file, write_csv
from ecadin_energy.dashboard.staging import DETERMINISTIC_FILES
from ecadin_energy.forecasting.configuration import load_production_config


def _allowed_production_models(
    project_root: str | Path | None,
) -> tuple[set[str], set[str]]:
    root = Path(project_root).resolve() if project_root else PATHS.root
    allowed_demand = {"demand_production_drift"}
    allowed_supply = {
        "supply_production_drift_v1",
        "supply_production_national_reconciled_v2",
    }
    cfg_path = root / "configs/forecasting/production.json"
    if cfg_path.is_file():
        forecast_cfg = load_production_config(cfg_path, project_root=root)
        allowed_demand.add(forecast_cfg.demand.production_model_id)
        allowed_supply.add(forecast_cfg.supply.production_model_id)
    return allowed_demand, allowed_supply


def validate_dashboard_directory(
    directory: Path,
    *,
    project_root: str | Path | None = None,
    config_path: str | Path | None = None,
) -> pd.DataFrame:
    config = load_dashboard_config(config_path, project_root=project_root)
    required = [directory / name for name in DETERMINISTIC_FILES]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("Dashboard outputs missing:\n- " + "\n- ".join(missing))

    detail = pd.read_csv(directory / "dashboard_province_detail.csv", low_memory=False)
    national = pd.read_csv(directory / "dashboard_national_timeseries.csv", low_memory=False)
    models = pd.read_csv(directory / "dashboard_model_summary.csv", low_memory=False)
    payload = json.loads((directory / "dashboard-production.json").read_text(encoding="utf-8"))
    registry = json.loads((directory / "dashboard_source_registry.json").read_text(encoding="utf-8"))

    checks: list[dict[str, object]] = []
    def add(check_id: str, passed: bool, observed: object, expected: object, details: str) -> None:
        checks.append({
            "check_id": check_id, "passed": bool(passed), "observed": str(observed),
            "expected": str(expected), "details": details,
        })

    add("region_year_contract", len(detail) == 680 and detail["region_id"].nunique() == 34,
        f"rows={len(detail)}, regions={detail['region_id'].nunique()}", "rows=680, regions=34",
        "One row per harmonized region and year, 2011-2030.")
    add("national_timeseries_contract", len(national) == 20 and national["year"].tolist() == list(range(2011, 2031)),
        f"rows={len(national)}", "20 rows, years 2011-2030", "National totals use complete demand-supply pairs.")
    complete = detail["available"].astype(str).str.lower().eq("true")
    historical = detail["data_type"].eq("historical")
    forecast = detail["data_type"].eq("forecast")
    add("completeness_contract", int(complete.sum()) == 671 and int((historical & ~complete).sum()) == 9 and int((forecast & ~complete).sum()) == 0,
        f"complete={complete.sum()}, historical_missing={(historical & ~complete).sum()}, forecast_missing={(forecast & ~complete).sum()}",
        "complete=671, historical_missing=9, forecast_missing=0", "Missing historical pairs stay explicit.")
    allowed_demand, allowed_supply = _allowed_production_models(project_root)
    demand_rows = models.loc[models["side"].eq("demand"), "model_version"].astype(str)
    supply_rows = models.loc[models["side"].eq("supply"), "model_version"].astype(str)
    model_contract_ok = (
        len(models) == 2
        and len(demand_rows) == 1
        and len(supply_rows) == 1
        and demand_rows.iloc[0] in allowed_demand
        and supply_rows.iloc[0] in allowed_supply
    )
    add("production_model_contract", model_contract_ok,
        sorted(models["model_version"].tolist()),
        sorted(allowed_demand | allowed_supply),
        "Only validated production models are published.")
    add("frontend_payload_contract", payload.get("schema_version") == config.frontend_schema_version and payload.get("row_count") == 680 and len(payload.get("provinces", [])) == 34,
        [payload.get("schema_version"), payload.get("row_count"), len(payload.get("provinces", []))],
        [config.frontend_schema_version, 680, 34], "Payload remains compatible with the finalized React frontend.")
    add("interpretation_contract", registry.get("accounting_disclaimer") == config.accounting_disclaimer and payload.get("legacy_ridge_used") is False and payload.get("regional_uncertainty_display_allowed") is False,
        [registry.get("accounting_disclaimer"), payload.get("legacy_ridge_used"), payload.get("regional_uncertainty_display_allowed")],
        [config.accounting_disclaimer, False, False], "Accounting difference is not an adequacy indicator.")

    expected_categories = [
        classify_accounting_difference(value if pd.notna(value) else None, config)
        for value in pd.to_numeric(detail["difference_to_demand_percent"], errors="coerce")
    ]
    add("category_contract", expected_categories == detail["gap_category"].astype(str).tolist(),
        sum(a != b for a, b in zip(expected_categories, detail["gap_category"].astype(str))), 0,
        "Threshold classification is stable and exact.")

    flattened = [point for province in payload["provinces"] for point in province["series"]]
    add("frontend_null_preservation", sum(1 for row in flattened if not row["available"] and row["gap_gwh"] is None) == 9,
        sum(1 for row in flattened if not row["available"] and row["gap_gwh"] is None), 9,
        "Incomplete values remain JSON null, never zero.")
    add("population_backlog_contract", all(province["population_2030_jiwa"] is None for province in payload["provinces"]) and all(point["population_jiwa"] is None for point in flattened),
        "all null" if all(province["population_2030_jiwa"] is None for province in payload["provinces"]) else "non-null found",
        "all null", "Population/per-capita are explicitly backlog.")

    frame = pd.DataFrame(checks)
    failures = frame.loc[~frame["passed"]]
    if not failures.empty:
        raise DashboardContractError("Dashboard validation failed:\n" + failures.to_string(index=False))
    return frame


def validate_dashboard_staging(
    *,
    project_root: str | Path | None = None,
    config_path: str | Path | None = None,
) -> pd.DataFrame:
    config = load_dashboard_config(config_path, project_root=project_root)
    paths = config.paths(project_root)
    checks = validate_dashboard_directory(paths.staging, project_root=paths.root, config_path=config_path)
    paths.reports.mkdir(parents=True, exist_ok=True)
    write_csv(checks, paths.reports / "dashboard_staging_checks.csv")
    return checks


def validate_dashboard_production(
    *,
    project_root: str | Path | None = None,
    config_path: str | Path | None = None,
) -> pd.DataFrame:
    config = load_dashboard_config(config_path, project_root=project_root)
    paths = config.paths(project_root)
    checks = validate_dashboard_directory(paths.production, project_root=paths.root, config_path=config_path)
    write_csv(checks, paths.reports / "dashboard_production_checks.csv")
    return checks
