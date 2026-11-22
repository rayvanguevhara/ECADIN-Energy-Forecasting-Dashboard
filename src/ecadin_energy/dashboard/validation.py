from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ecadin_energy.config import PATHS
from ecadin_energy.dashboard.configuration import DashboardConfig, load_dashboard_config
from ecadin_energy.dashboard.contracts import DashboardContractError
from ecadin_energy.dashboard.data_quality import QUALITY_FLAGS_SUMMARY_COLUMNS
from ecadin_energy.dashboard.national_overview import build_national_timeseries
from ecadin_energy.dashboard.region_detail import (
    ATTENTION_REASON_MAP,
    VALID_GAP_CATEGORIES,
    classify_accounting_difference,
)
from ecadin_energy.dashboard.serializers import (
    is_relative_posix_path,
    sha256_file,
    write_csv,
)
from ecadin_energy.dashboard.staging import (
    DETERMINISTIC_DATA_FILES,
    DETERMINISTIC_FILES,
    OUTPUT_HASH_MANIFEST_FILE,
)
from ecadin_energy.forecasting.configuration import load_production_config


def _to_bool_series(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False).astype(bool)
    return (
        series.astype("string")
        .str.strip()
        .str.lower()
        .eq("true")
        .fillna(False)
    )


def _expected_production_models(root: Path) -> tuple[set[str], set[str]]:
    model_summary_path = root / "outputs/production/metrics/production_model_summary.csv"
    contract_checks_path = root / "outputs/production/reports/production_contract_checks.csv"
    if model_summary_path.is_file() and contract_checks_path.is_file():
        contracts = pd.read_csv(contract_checks_path, low_memory=False)
        if not contracts.empty and _to_bool_series(contracts["passed"]).all():
            summary = pd.read_csv(model_summary_path, low_memory=False)
            selected = summary.loc[_to_bool_series(summary["selected_for_production"])]
            demand_ids = set(
                selected.loc[selected["domain"].astype(str).eq("demand"), "production_model_id"]
                .astype(str)
                .tolist()
            )
            supply_ids = set(
                selected.loc[selected["domain"].astype(str).eq("supply"), "production_model_id"]
                .astype(str)
                .tolist()
            )
            if demand_ids and supply_ids:
                return demand_ids, supply_ids

    cfg_path = root / "configs/forecasting/production.json"
    if cfg_path.is_file():
        forecast_cfg = load_production_config(cfg_path, project_root=root)
        return (
            {forecast_cfg.demand.production_model_id},
            {forecast_cfg.supply.production_model_id},
        )
    raise FileNotFoundError(
        "Neither production_model_summary.csv nor configs/forecasting/production.json found"
    )


def _verify_output_hashes(
    directory: Path,
    registry: dict[str, object],
    payload: dict[str, object],
) -> tuple[bool, str, str, str]:
    manifest_path = directory / OUTPUT_HASH_MANIFEST_FILE
    if not manifest_path.is_file():
        return (
            False,
            f"missing {OUTPUT_HASH_MANIFEST_FILE}",
            f"verified={len(DETERMINISTIC_DATA_FILES)}/{len(DETERMINISTIC_DATA_FILES)}",
            f"Missing output hash manifest: {OUTPUT_HASH_MANIFEST_FILE}",
        )

    manifest = pd.read_csv(manifest_path, low_memory=False)
    required_cols = {"artifact_id", "relative_path", "size_bytes", "sha256"}
    if not required_cols.issubset(manifest.columns) or manifest.empty:
        return (
            False,
            f"columns={list(manifest.columns)}, rows={len(manifest)}",
            f"columns={sorted(required_cols)}",
            "Invalid dashboard_output_hashes.csv schema or empty manifest.",
        )

    errors: list[str] = []
    manifest_paths = manifest["relative_path"].astype(str).tolist()
    expected_set = set(DETERMINISTIC_DATA_FILES)
    if set(manifest_paths) != expected_set or len(manifest_paths) != len(expected_set):
        errors.append(
            f"manifest file set mismatch: got={sorted(manifest_paths)} expected={sorted(expected_set)}"
        )

    verified = 0
    total = len(DETERMINISTIC_DATA_FILES)
    for record in manifest.to_dict(orient="records"):
        artifact_id = str(record["artifact_id"])
        rel_path = record["relative_path"]
        expected_size = int(record["size_bytes"])
        expected_sha = str(record["sha256"]).strip().upper()
        if not is_relative_posix_path(rel_path):
            errors.append(f"{artifact_id}: non-relative path '{rel_path}'")
            continue
        target = directory / str(rel_path)
        if not target.is_file():
            errors.append(f"{artifact_id}: missing file {rel_path}")
            continue
        actual_sha = sha256_file(target)
        actual_size = target.stat().st_size
        if actual_sha != expected_sha or actual_size != expected_size:
            errors.append(
                f"{artifact_id} ({rel_path}): expected sha256={expected_sha} size={expected_size}, "
                f"got sha256={actual_sha} size={actual_size}"
            )
            continue
        verified += 1

    payload_file = directory / "dashboard-production.json"
    actual_payload_sha = sha256_file(payload_file)
    reg_payload_sha = str(registry.get("payload_sha256", "")).strip().upper()
    if registry.get("payload_relative_path") != "dashboard-production.json" or reg_payload_sha != actual_payload_sha:
        errors.append(
            f"registry payload_sha256 mismatch: expected={actual_payload_sha}, got={reg_payload_sha}"
        )
    if registry.get("source_hashes") != payload.get("source_hashes"):
        errors.append("registry source_hashes does not match payload source_hashes")

    return (
        len(errors) == 0,
        f"verified={verified}/{total}",
        f"verified={total}/{total}",
        (
            f"All {total} deterministic dashboard output SHA-256 hashes verified."
            if not errors
            else "; ".join(errors)
        ),
    )


def _verify_input_hashes(
    directory: Path,
    root: Path,
    registry: dict[str, object],
    payload: dict[str, object],
    *,
    verify_against_disk: bool,
) -> tuple[bool, str, str, str]:
    manifest_path = directory / "dashboard_input_hashes.csv"
    manifest = pd.read_csv(manifest_path, low_memory=False)
    required_cols = {"source_id", "relative_path", "size_bytes", "sha256"}
    if not required_cols.issubset(manifest.columns) or manifest.empty:
        return (
            False,
            f"columns={list(manifest.columns)}, rows={len(manifest)}",
            f"columns={sorted(required_cols)}",
            "Invalid dashboard_input_hashes.csv schema or empty manifest.",
        )

    errors: list[str] = []
    manifest_map: dict[str, str] = {}
    verified = 0
    total = int(len(manifest))
    for record in manifest.to_dict(orient="records"):
        source_id = str(record["source_id"])
        rel_path = record["relative_path"]
        expected_size = int(record["size_bytes"])
        expected_sha = str(record["sha256"]).strip().upper()
        if not is_relative_posix_path(rel_path):
            errors.append(f"{source_id}: non-relative path '{rel_path}'")
            continue
        manifest_map[str(rel_path)] = expected_sha
        if verify_against_disk:
            target = root / str(rel_path)
            if not target.is_file():
                errors.append(f"{source_id}: missing upstream file {rel_path}")
                continue
            actual_sha = sha256_file(target)
            actual_size = target.stat().st_size
            if actual_sha != expected_sha or actual_size != expected_size:
                errors.append(
                    f"{source_id} ({rel_path}): expected sha256={expected_sha} size={expected_size}, "
                    f"got sha256={actual_sha} size={actual_size}"
                )
                continue
        verified += 1

    if registry.get("source_hashes") != manifest_map:
        errors.append("registry source_hashes does not match dashboard_input_hashes.csv")
    if payload.get("source_hashes") != manifest_map:
        errors.append("payload source_hashes does not match dashboard_input_hashes.csv")

    return (
        len(errors) == 0,
        f"verified={verified}/{total}",
        f"verified={total}/{total}",
        (
            f"All {total} dashboard input SHA-256 hashes verified."
            if not errors
            else "; ".join(errors)
        ),
    )


def validate_dashboard_directory(
    directory: Path,
    *,
    project_root: str | Path | None = None,
    config_path: str | Path | None = None,
    verify_input_hashes_against_disk: bool = True,
) -> pd.DataFrame:
    """Validate all deterministic dashboard artifacts, cross-consistency, and SHA-256 hashes."""
    root = Path(project_root).resolve() if project_root else PATHS.root
    config: DashboardConfig = load_dashboard_config(config_path, project_root=root)
    required = [directory / name for name in DETERMINISTIC_FILES]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("Dashboard outputs missing:\n- " + "\n- ".join(missing))

    detail = pd.read_csv(directory / "dashboard_province_detail.csv", low_memory=False)
    national = pd.read_csv(directory / "dashboard_national_timeseries.csv", low_memory=False)
    map_frame = pd.read_csv(directory / "dashboard_map_timeseries.csv", low_memory=False)
    ranking = pd.read_csv(directory / "dashboard_regional_ranking.csv", low_memory=False)
    models = pd.read_csv(directory / "dashboard_model_summary.csv", low_memory=False)
    quality_summary = pd.read_csv(directory / "dashboard_data_quality_summary.csv", low_memory=False)
    quality_review = pd.read_csv(directory / "dashboard_data_quality_review.csv", low_memory=False)
    flags_summary = pd.read_csv(
        directory / "dashboard_data_quality_flags_summary.csv", low_memory=False
    )
    methodology = json.loads((directory / "dashboard_methodology.json").read_text(encoding="utf-8"))
    payload = json.loads((directory / "dashboard-production.json").read_text(encoding="utf-8"))
    registry = json.loads((directory / "dashboard_source_registry.json").read_text(encoding="utf-8"))

    expected_years = list(config.years)
    expected_rows = config.expected_regions * len(expected_years)

    checks: list[dict[str, object]] = []

    def add(
        check_id: str,
        passed: bool,
        observed: object,
        expected: object,
        details: str,
    ) -> None:
        checks.append(
            {
                "check_id": check_id,
                "passed": bool(passed),
                "observed": str(observed),
                "expected": str(expected),
                "details": details,
            }
        )

    detail_years = sorted(pd.to_numeric(detail["year"], errors="coerce").dropna().astype(int).unique().tolist())
    no_dups = not detail.duplicated(["region_id", "year"]).any()
    add(
        "region_year_contract",
        len(detail) == expected_rows
        and detail["region_id"].nunique() == config.expected_regions
        and detail_years == expected_years
        and no_dups,
        f"rows={len(detail)}, regions={detail['region_id'].nunique()}, years={detail_years[:1]}..{detail_years[-1:]}",
        f"rows={expected_rows}, regions={config.expected_regions}, years={expected_years[0]}..{expected_years[-1]}",
        f"One row per harmonized region and year, {expected_years[0]}-{expected_years[-1]}.",
    )

    recomputed_national = build_national_timeseries(detail, config.expected_regions)
    nat_years = pd.to_numeric(national["year"], errors="coerce").astype("Int64").tolist()
    nat_common_actual = (
        pd.to_numeric(national["yoy_common_regions"], errors="coerce").fillna(-1).astype(int).tolist()
        if "yoy_common_regions" in national.columns
        else []
    )
    nat_common_expected = (
        pd.to_numeric(recomputed_national["yoy_common_regions"], errors="coerce")
        .fillna(-1)
        .astype(int)
        .tolist()
    )
    nat_match = (
        len(national) == len(expected_years)
        and nat_years == expected_years
        and "yoy_common_regions" in national.columns
        and "yoy_basis" in national.columns
        and national["complete_regions"].astype(int).tolist()
        == recomputed_national["complete_regions"].astype(int).tolist()
        and national["total_regions"].astype(int).tolist()
        == recomputed_national["total_regions"].astype(int).tolist()
        and national["data_completeness"].astype(str).tolist()
        == recomputed_national["data_completeness"].astype(str).tolist()
        and national["yoy_basis"].astype(str).tolist()
        == recomputed_national["yoy_basis"].astype(str).tolist()
        and nat_common_actual == nat_common_expected
        and all(
            np.allclose(
                pd.to_numeric(national[col], errors="coerce").to_numpy(dtype=float),
                pd.to_numeric(recomputed_national[col], errors="coerce").to_numpy(dtype=float),
                rtol=1e-9,
                atol=1e-6,
                equal_nan=True,
            )
            for col in (
                "demand_gwh",
                "supply_gwh",
                "accounting_difference_gwh",
                "demand_growth_yoy_percent",
                "supply_growth_yoy_percent",
            )
        )
    )
    add(
        "national_timeseries_contract",
        nat_match,
        f"rows={len(national)}, years={nat_years[:1]}..{nat_years[-1:]}",
        f"{len(expected_years)} rows, years {expected_years[0]}-{expected_years[-1]}, matched YoY",
        "National totals and matched-region YoY growth match detail complete pairs.",
    )

    complete = _to_bool_series(detail["available"])
    demand_num = pd.to_numeric(detail["demand_gwh"], errors="coerce")
    supply_num = pd.to_numeric(detail["supply_gwh"], errors="coerce")
    actual_complete_mask = demand_num.notna() & supply_num.notna()
    historical = detail["data_type"].astype(str).eq("historical")
    forecast = detail["data_type"].astype(str).eq("forecast")
    expected_complete_pairs = int(actual_complete_mask.sum())
    expected_historical_missing = int((historical & ~actual_complete_mask).sum())
    add(
        "completeness_contract",
        bool((complete == actual_complete_mask).all())
        and int(complete.sum()) == expected_complete_pairs
        and int((historical & ~complete).sum()) == expected_historical_missing
        and int((forecast & ~complete).sum()) == 0
        and payload.get("complete_gap_count") == expected_complete_pairs
        and payload.get("historical_incomplete_gap_count") == expected_historical_missing,
        f"complete={int(complete.sum())}, historical_missing={int((historical & ~complete).sum())}, forecast_missing={int((forecast & ~complete).sum())}",
        f"complete={expected_complete_pairs}, historical_missing={expected_historical_missing}, forecast_missing=0",
        "Missing historical pairs stay explicit across detail and payload.",
    )

    allowed_demand, allowed_supply = _expected_production_models(root)
    demand_rows = models.loc[models["side"].astype(str).eq("demand"), "model_version"].astype(str)
    supply_rows = models.loc[models["side"].astype(str).eq("supply"), "model_version"].astype(str)
    forecast_demand_models = set(detail.loc[forecast, "demand_model"].astype(str).unique())
    forecast_supply_models = set(detail.loc[forecast, "supply_model"].astype(str).unique())
    metadata_v2 = payload.get("metadata_v2", {})
    meth_models = methodology.get("production_models", {})
    payload_models_map = {
        str(item.get("side")): str(item.get("model_version"))
        for item in payload.get("models", [])
    }
    model_contract_ok = (
        len(models) == 2
        and len(demand_rows) == 1
        and len(supply_rows) == 1
        and demand_rows.iloc[0] in allowed_demand
        and supply_rows.iloc[0] in allowed_supply
        and forecast_demand_models == {demand_rows.iloc[0]}
        and forecast_supply_models == {supply_rows.iloc[0]}
        and metadata_v2.get("demand_model") == demand_rows.iloc[0]
        and metadata_v2.get("supply_model") == supply_rows.iloc[0]
        and meth_models.get("demand_model_id") == demand_rows.iloc[0]
        and meth_models.get("supply_model_id") == supply_rows.iloc[0]
        and payload_models_map == {"demand": demand_rows.iloc[0], "supply": supply_rows.iloc[0]}
    )
    add(
        "production_model_contract",
        model_contract_ok,
        sorted(models["model_version"].astype(str).tolist()),
        sorted(allowed_demand | allowed_supply),
        "Only validated production models are published and cross-consistent across detail, payload, and methodology.",
    )

    flattened = [
        point
        for province in payload.get("provinces", [])
        for point in province.get("series", [])
    ]
    add(
        "frontend_payload_contract",
        payload.get("schema_version") == config.frontend_schema_version
        and payload.get("row_count") == expected_rows
        and payload.get("region_count") == config.expected_regions
        and len(payload.get("provinces", [])) == config.expected_regions
        and len(payload.get("national", [])) == len(expected_years)
        and payload.get("period") == [config.history_start_year, config.forecast_end_year]
        and payload.get("forecast_start") == config.forecast_start_year
        and len(flattened) == expected_rows,
        [
            payload.get("schema_version"),
            payload.get("row_count"),
            len(payload.get("provinces", [])),
            len(payload.get("national", [])),
        ],
        [
            config.frontend_schema_version,
            expected_rows,
            config.expected_regions,
            len(expected_years),
        ],
        "Payload remains compatible with the React frontend contract.",
    )

    legacy_clarification = (
        methodology.get("contract_clarifications", {}).get("legacy_ridge_used", {})
    )
    add(
        "interpretation_contract",
        registry.get("accounting_disclaimer") == config.accounting_disclaimer
        and methodology.get("accounting_disclaimer") == config.accounting_disclaimer
        and payload.get("legacy_ridge_used") is config.legacy_model_reused
        and payload.get("regional_uncertainty_display_allowed")
        is config.regional_uncertainty_display_allowed
        and legacy_clarification.get("value") is config.legacy_model_reused
        and bool(legacy_clarification.get("meaning")),
        [
            registry.get("accounting_disclaimer") == config.accounting_disclaimer,
            payload.get("legacy_ridge_used"),
            payload.get("regional_uncertainty_display_allowed"),
        ],
        [
            True,
            config.legacy_model_reused,
            config.regional_uncertainty_display_allowed,
        ],
        "Accounting difference is not an adequacy indicator and legacy_ridge_used meaning is documented.",
    )

    expected_categories = [
        classify_accounting_difference(value if pd.notna(value) else None, config)
        for value in pd.to_numeric(detail["difference_to_demand_percent"], errors="coerce")
    ]
    detail_cats = detail["gap_category"].astype(str).tolist()
    payload_cats = [str(point.get("gap_category")) for point in flattened]
    valid_cat_set = set(VALID_GAP_CATEGORIES)
    valid_reason_set = set(ATTENTION_REASON_MAP.values())
    detail_reasons = detail["attention_reason"].dropna().astype(str)
    payload_reasons = [
        str(point["attention_reason"])
        for point in flattened
        if point.get("attention_reason") is not None
    ]
    category_ok = (
        expected_categories == detail_cats
        and set(detail_cats).issubset(valid_cat_set)
        and set(payload_cats).issubset(valid_cat_set)
        and detail_reasons.isin(valid_reason_set).all()
        and set(payload_reasons).issubset(valid_reason_set)
    )
    add(
        "category_contract",
        category_ok,
        sum(a != b for a, b in zip(expected_categories, detail_cats)),
        0,
        "Neutral accounting gap categories and attention reasons are consistent across detail and payload.",
    )

    add(
        "frontend_null_preservation",
        sum(1 for row in flattened if not row["available"] and row["gap_gwh"] is None)
        == expected_historical_missing,
        sum(1 for row in flattened if not row["available"] and row["gap_gwh"] is None),
        expected_historical_missing,
        "Incomplete values remain JSON null, never zero.",
    )

    add(
        "population_backlog_contract",
        all(province["population_2030_jiwa"] is None for province in payload["provinces"])
        and all(point["population_jiwa"] is None for point in flattened),
        "all null"
        if all(province["population_2030_jiwa"] is None for province in payload["provinces"])
        else "non-null found",
        "all null",
        "Population/per-capita remain explicitly backlog.",
    )

    r_demand_na = pd.to_numeric(ranking["demand_gwh"], errors="coerce").isna()
    r_supply_na = pd.to_numeric(ranking["supply_gwh"], errors="coerce").isna()
    r_avail = _to_bool_series(ranking["available"])
    r_d_rank = pd.to_numeric(ranking["demand_rank_desc"], errors="coerce")
    r_s_rank = pd.to_numeric(ranking["supply_rank_desc"], errors="coerce")
    r_g_rank = pd.to_numeric(ranking["difference_rank_desc"], errors="coerce")
    ranking_ok = (
        len(ranking) == expected_rows
        and list(zip(ranking["region_id"], ranking["year"]))
        == list(zip(detail["region_id"], detail["year"]))
        and bool(r_d_rank[r_demand_na].isna().all())
        and bool(r_d_rank[~r_demand_na].notna().all() and (r_d_rank[~r_demand_na] >= 1).all())
        and bool(r_s_rank[r_supply_na].isna().all())
        and bool(r_s_rank[~r_supply_na].notna().all() and (r_s_rank[~r_supply_na] >= 1).all())
        and bool(r_g_rank[~r_avail].isna().all())
        and bool(r_g_rank[r_avail].notna().all() and (r_g_rank[r_avail] >= 1).all())
        and set(ranking["gap_category"].astype(str)).issubset(valid_cat_set)
    )
    add(
        "regional_ranking_contract",
        ranking_ok,
        f"rows={len(ranking)}, demand_na_ranked={int(r_d_rank[r_demand_na].notna().sum())}, supply_na_ranked={int(r_s_rank[r_supply_na].notna().sum())}",
        f"rows={expected_rows}, demand_na_ranked=0, supply_na_ranked=0",
        "Regional ranking enforces unranked NA on missing metrics and aligns with detail keys.",
    )

    expected_review_count = int(
        (detail["quality"].astype(str).ne("observed") | _to_bool_series(detail["attention"])).sum()
    )
    review_reasons = quality_review["attention_reason"].dropna().astype(str)
    flags_sum = int(
        pd.to_numeric(flags_summary["flag_count"], errors="coerce").fillna(0).sum()
    )
    map_quality_ok = (
        len(map_frame) == expected_rows
        and map_frame["region_id"].nunique() == config.expected_regions
        and map_frame["gap_category"].astype(str).tolist() == detail_cats
        and bool(pd.to_numeric(map_frame["latitude"], errors="coerce").notna().all())
        and bool(pd.to_numeric(map_frame["longitude"], errors="coerce").notna().all())
        and int(pd.to_numeric(quality_summary["region_rows"], errors="raise").sum()) == expected_rows
        and len(quality_review) == expected_review_count
        and bool(review_reasons.isin(valid_reason_set).all())
        and set(QUALITY_FLAGS_SUMMARY_COLUMNS).issubset(flags_summary.columns)
        and flags_sum == payload.get("quality_flags_total")
    )
    add(
        "map_and_quality_artifacts_contract",
        map_quality_ok,
        f"map_rows={len(map_frame)}, quality_rows={int(pd.to_numeric(quality_summary['region_rows'], errors='coerce').sum())}, flags={flags_sum}",
        f"map_rows={expected_rows}, quality_rows={expected_rows}, flags={payload.get('quality_flags_total')}",
        "Map timeseries, data quality summary/review, and data quality flags summary are consistent.",
    )

    out_ok, out_obs, out_exp, out_det = _verify_output_hashes(directory, registry, payload)
    add("output_hashes_sha256", out_ok, out_obs, out_exp, out_det)

    in_ok, in_obs, in_exp, in_det = _verify_input_hashes(
        directory,
        root,
        registry,
        payload,
        verify_against_disk=verify_input_hashes_against_disk,
    )
    add("input_hashes_sha256", in_ok, in_obs, in_exp, in_det)

    frame = pd.DataFrame(checks)
    failures = frame.loc[~frame["passed"]]
    if not failures.empty:
        raise DashboardContractError(
            "Dashboard validation failed:\n" + failures.to_string(index=False)
        )
    return frame


def validate_dashboard_staging(
    *,
    project_root: str | Path | None = None,
    config_path: str | Path | None = None,
) -> pd.DataFrame:
    config = load_dashboard_config(config_path, project_root=project_root)
    paths = config.paths(project_root)
    checks = validate_dashboard_directory(
        paths.staging,
        project_root=paths.root,
        config_path=config_path,
    )
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
    checks = validate_dashboard_directory(
        paths.production,
        project_root=paths.root,
        config_path=config_path,
    )
    paths.reports.mkdir(parents=True, exist_ok=True)
    write_csv(checks, paths.reports / "dashboard_production_checks.csv")
    return checks
