from __future__ import annotations

from typing import Any

import pandas as pd

from ecadin_energy.config import PATHS
from ecadin_energy.dashboard.configuration import DashboardConfig
from ecadin_energy.dashboard.serializers import clean_scalar
from ecadin_energy.forecasting.configuration import ProductionConfig, load_production_config


def _format_year_span(years: tuple[int, ...]) -> str:
    if not years:
        return ""
    return f"{min(years)}-{max(years)}" if len(years) > 1 else str(years[0])


def _default_forecast_config() -> ProductionConfig | None:
    cfg_path = PATHS.root / "configs/forecasting/production.json"
    if cfg_path.is_file():
        return load_production_config(cfg_path, project_root=PATHS.root)
    return None


def _resolve_model_info(
    side: str,
    models: pd.DataFrame | None,
    forecast_config: ProductionConfig | None,
) -> dict[str, Any]:
    domain_cfg = forecast_config.domain_config(side) if forecast_config is not None else None
    info: dict[str, Any] = {
        "side": side,
        "model_id": (
            domain_cfg.production_model_id
            if domain_cfg is not None
            else (
                "demand_production_drift"
                if side == "demand"
                else "supply_production_national_reconciled_v2"
            )
        ),
        "active_model": (
            domain_cfg.model_name
            if domain_cfg is not None
            else ("drift" if side == "demand" else "national_reconciled_supply")
        ),
        "model_label": (
            domain_cfg.model_label
            if domain_cfg is not None
            else (
                "Drift"
                if side == "demand"
                else "National Reconciled Supply (Drift National -> Step Intervention Damped)"
            )
        ),
        "evaluated_backtest_model_count": (
            len(forecast_config.evaluated_models_for_domain(side))
            if forecast_config is not None
            else (4 if side == "demand" else 5)
        ),
        "evaluated_models": (
            list(forecast_config.evaluated_models_for_domain(side))
            if forecast_config is not None
            else []
        ),
        "rolling_metrics": None,
        "recursive_metrics": None,
        "params": None,
    }

    if domain_cfg is not None and domain_cfg.model_params is not None:
        info["params"] = {
            "break_year": int(domain_cfg.model_params.break_year),
            "ridge_lambda": float(domain_cfg.model_params.ridge_lambda),
            "damping_phi": float(domain_cfg.model_params.damping_phi),
            "national_start_year": int(domain_cfg.model_params.national_start_year),
        }

    if models is None or models.empty:
        return info

    if "side" in models.columns:
        subset = models.loc[models["side"].astype(str).eq(side)]
        if not subset.empty:
            row = subset.iloc[0]
            model_id = str(row["model_version"])
            active_model = str(row["active_model"])
            info["model_id"] = model_id
            info["active_model"] = active_model
            if "model_label" in subset.columns and pd.notna(row.get("model_label")):
                info["model_label"] = str(row["model_label"])
            elif domain_cfg is not None and domain_cfg.production_model_id == model_id:
                info["model_label"] = domain_cfg.model_label
            else:
                info["model_label"] = (
                    "National Reconciled Supply (Drift National -> Step Intervention Damped)"
                    if active_model == "national_reconciled_supply"
                    else "Drift"
                )
            if "evaluated_backtest_model_count" in subset.columns and pd.notna(
                row.get("evaluated_backtest_model_count")
            ):
                info["evaluated_backtest_model_count"] = int(
                    row["evaluated_backtest_model_count"]
                )
            elif forecast_config is not None and (
                domain_cfg is None or domain_cfg.production_model_id != model_id
            ):
                info["evaluated_backtest_model_count"] = len(forecast_config.baseline_models)
                info["evaluated_models"] = list(forecast_config.baseline_models)

            if pd.notna(row.get("rolling_macro_smape_percent")):
                info["rolling_metrics"] = {
                    "prediction_count": clean_scalar(row.get("rolling_prediction_count")),
                    "macro_smape_percent": clean_scalar(row.get("rolling_macro_smape_percent")),
                    "macro_mase": clean_scalar(row.get("rolling_macro_mase")),
                    "micro_rmse_gwh": clean_scalar(row.get("rolling_micro_rmse_gwh")),
                    "aggregate_bias_percent": clean_scalar(
                        row.get("rolling_aggregate_bias_percent")
                    ),
                }
            if pd.notna(row.get("recursive_macro_smape_percent")):
                info["recursive_metrics"] = {
                    "prediction_count": clean_scalar(row.get("recursive_prediction_count")),
                    "macro_smape_percent": clean_scalar(
                        row.get("recursive_macro_smape_percent")
                    ),
                    "macro_mase": clean_scalar(row.get("recursive_macro_mase")),
                    "micro_rmse_gwh": clean_scalar(row.get("recursive_micro_rmse_gwh")),
                    "aggregate_bias_percent": clean_scalar(
                        row.get("recursive_aggregate_bias_percent")
                    ),
                }
            if active_model == "national_reconciled_supply":
                if pd.notna(row.get("break_year")) and pd.notna(row.get("ridge_lambda")):
                    info["params"] = {
                        "break_year": int(row["break_year"]),
                        "ridge_lambda": float(row["ridge_lambda"]),
                        "damping_phi": float(row["damping_phi"]),
                        "national_start_year": int(row["national_start_year"]),
                    }
            else:
                info["params"] = None
    elif "domain" in models.columns:
        selected = models.loc[
            models["selected_for_production"].astype(str).str.lower().eq("true")
            & models["domain"].astype(str).eq(side)
        ]
        if not selected.empty:
            model_id = str(selected["production_model_id"].iloc[0])
            info["model_id"] = model_id
            if "model_label" in selected.columns and pd.notna(
                selected["model_label"].iloc[0]
            ):
                info["model_label"] = str(selected["model_label"].iloc[0])
            if domain_cfg is not None and domain_cfg.production_model_id == model_id:
                info["active_model"] = domain_cfg.model_name
            else:
                info["active_model"] = (
                    "national_reconciled_supply"
                    if "national_reconciled" in model_id
                    else "drift"
                )
                if info["active_model"] != "national_reconciled_supply":
                    info["params"] = None
                    if forecast_config is not None:
                        info["evaluated_backtest_model_count"] = len(
                            forecast_config.baseline_models
                        )
                        info["evaluated_models"] = list(forecast_config.baseline_models)
            for proto, target_key in (
                ("rolling_one_step", "rolling_metrics"),
                ("recursive_multi_step", "recursive_metrics"),
            ):
                p_row = selected.loc[selected["protocol"].astype(str).eq(proto)]
                if not p_row.empty:
                    r0 = p_row.iloc[0]
                    info[target_key] = {
                        "prediction_count": clean_scalar(r0.get("prediction_count")),
                        "macro_smape_percent": clean_scalar(r0.get("macro_smape_percent")),
                        "macro_mase": clean_scalar(r0.get("macro_mase")),
                        "micro_rmse_gwh": clean_scalar(r0.get("micro_rmse_gwh")),
                        "aggregate_bias_percent": clean_scalar(
                            r0.get("aggregate_bias_percent")
                        ),
                    }
    return info


def _build_supply_specification(supply_info: dict[str, Any]) -> dict[str, Any]:
    if supply_info["active_model"] == "national_reconciled_supply":
        params = supply_info["params"] or {
            "break_year": 2021,
            "ridge_lambda": 25.0,
            "damping_phi": 0.85,
            "national_start_year": 2013,
        }
        return {
            "model_class": "Hierarchical National-Reconciled + FWL Step-Intervention Damped",
            "formula": (
                f"National Drift over t >= {params['national_start_year']} reconciled proportionally "
                f"across regional FWL step-intervention damped forecasts with break dummy "
                f"I(t >= {params['break_year']}), Ridge slope damping lambda={params['ridge_lambda']}, "
                f"and geometric damping phi={params['damping_phi']}."
            ),
            "parameters": params,
            "evaluated_backtest_models": supply_info["evaluated_backtest_model_count"],
            "rolling_metrics": supply_info["rolling_metrics"],
            "recursive_metrics": supply_info["recursive_metrics"],
            "selection_basis": (
                "Promoted in Phase 3: #1 rolling one-step (29.05% sMAPE), 54.52% recursive h=1..3 "
                "(52.71% win rate vs Drift), #1 clean post-2021 origins (15.44% sMAPE), and 410,265.37 GWh "
                "national 2030 projection (+2.98% CAGR) removing 2021 administrative jump distortion."
            ),
        }
    return {
        "model_class": "Univariate annual endpoint Drift",
        "formula": "y_hat(T+h) = max(0, y_T + h * (y_T - y_t0) / (T - t0))",
        "parameters": {},
        "evaluated_backtest_models": supply_info["evaluated_backtest_model_count"],
        "rolling_metrics": supply_info["rolling_metrics"],
        "recursive_metrics": supply_info["recursive_metrics"],
        "selection_basis": "Active supply baseline model configured in production summary.",
    }


def build_methodology(
    config: DashboardConfig,
    *,
    models: pd.DataFrame | None = None,
    forecast_config: ProductionConfig | None = None,
) -> dict[str, object]:
    """Build full methodology JSON dynamically from active models and forecasting config."""
    fc_cfg = forecast_config if forecast_config is not None else _default_forecast_config()
    demand_info = _resolve_model_info("demand", models, fc_cfg)
    supply_info = _resolve_model_info("supply", models, fc_cfg)

    rolling_targets = (
        _format_year_span(fc_cfg.one_step_target_years) if fc_cfg is not None else "2019-2024"
    )
    recursive_origins = (
        _format_year_span(fc_cfg.recursive_origins) if fc_cfg is not None else "2018-2021"
    )
    recursive_max_horizon = int(fc_cfg.recursive_max_horizon) if fc_cfg is not None else 3

    return {
        "schema_version": "dashboard_methodology_v1",
        "definitions": {
            "demand": "Annual distributed electricity within a harmonized modeling region (GWh).",
            "supply": "Annual local electricity generation within the same harmonized region (GWh).",
            "accounting_difference": "Local generation minus distributed electricity.",
        },
        "production_models": {
            "demand": demand_info["model_label"],
            "demand_model_id": demand_info["model_id"],
            "demand_active_model": demand_info["active_model"],
            "demand_specification": {
                "model_class": "Univariate annual endpoint Drift",
                "formula": "y_hat(T+h) = max(0, y_T + h * (y_T - y_t0) / (T - t0))",
                "evaluated_backtest_models": demand_info["evaluated_backtest_model_count"],
                "rolling_metrics": demand_info["rolling_metrics"],
                "recursive_metrics": demand_info["recursive_metrics"],
                "selection_basis": (
                    "Retained #1 across rolling one-step (5.83% sMAPE), recursive h=1..3 "
                    "(8.14% sMAPE, MASE 1.256, aggregate bias -0.04%), and extended h=4..6 "
                    "(12.36% sMAPE) both with and without the KR 2020 outlier."
                ),
            },
            "supply": supply_info["model_label"],
            "supply_model_id": supply_info["model_id"],
            "supply_active_model": supply_info["active_model"],
            "supply_specification": _build_supply_specification(supply_info),
            "frequency": "annual",
            "historical_period": f"{config.history_start_year}-{config.history_end_year}",
            "forecast_period": f"{config.forecast_start_year}-{config.forecast_end_year}",
        },
        "validation": {
            "rolling_one_step_targets": rolling_targets,
            "recursive_origins": recursive_origins,
            "recursive_max_horizon": recursive_max_horizon,
            "evaluated_models": {
                "demand_count": demand_info["evaluated_backtest_model_count"],
                "demand_models": demand_info["evaluated_models"],
                "supply_count": supply_info["evaluated_backtest_model_count"],
                "supply_models": supply_info["evaluated_models"],
            },
            "metrics": [
                "macro_sMAPE",
                "macro_MASE",
                "micro_RMSE",
                "aggregate_bias",
                "challenger_win_rate_vs_Drift",
            ],
        },
        "data_treatment": {
            "year_2016": "Interpolated in modeling history only; not an observed validation target.",
            "other_missing": "Preserved as missing; never converted to zero.",
            "population": "Backlog; not integrated into the production dashboard data contract.",
            "ruptl": "Benchmark and scenario reference only; not a production target.",
            "national_yoy_growth": (
                "Computed over the matched intersection of complete demand-supply regions across "
                "consecutive years (common_regions = complete(t) ∩ complete(t-1))."
            ),
        },
        "phase2_benchmark_summary": {
            "total_evaluated_models": 26,
            "supply_candidates_evaluated": 14,
            "demand_candidates_evaluated": 12,
            "supply_selection": {
                "selected_model": supply_info["active_model"],
                "selected_model_id": supply_info["model_id"],
                "rolling_one_step_smape_percent": 29.05,
                "recursive_h3_smape_percent": 54.52,
                "recursive_win_rate_vs_drift_percent": 52.71,
                "post_2021_clean_origins_smape_percent": 15.44,
                "national_2030_projection_gwh": 410265.37,
                "national_2024_2030_cagr_percent": 2.98,
            },
            "demand_selection": {
                "selected_model": demand_info["active_model"],
                "selected_model_id": demand_info["model_id"],
                "rolling_one_step_smape_percent": 5.83,
                "recursive_h3_smape_percent": 8.14,
                "extended_h4_h6_smape_percent": 12.36,
                "national_2030_projection_gwh": 374291.69,
                "national_2024_2030_cagr_percent": 3.40,
            },
        },
        "adr_001_data_governance": {
            "reference": "ADR-001",
            "snapshot_policy": (
                "Canonical historical master (2011-2024, 476 region-year rows) is frozen to the "
                "verified BPS CSV snapshot without ad-hoc retrospective patching."
            ),
            "pdf_audit_2020_2024": {
                "total_cells_audited": 510,
                "exact_match": 478,
                "revision_candidate": 30,
                "canonical_missing_pdf_zero": 2,
                "demand_2020_2024_exact": "170/170",
                "supply_2021_2024_exact": "136/136",
            },
            "regime_shift_2021_stpl": (
                "BPS STPL questionnaire revision in 2021 (Blok III.301 Kab/Kota -> Blok IV.401 "
                "Prov/Kab/Kota + IPP) eliminated UIKL/UIK/UIP parent-province concentration, causing "
                "16 provincial YoY flags plus Sulawesi Barat zero-base jump (0 -> 249.45 GWh), "
                "independently cross-checked against ESDM Table 4."
            ),
            "kr_2020_anomaly": (
                "Kepulauan Riau 2020 distributed electricity contraction (-73.48%, 887.60 GWh) "
                "matches BPS/ESDM Table 25 records where PT PLN Batam (2,443.27 GWh) was reported "
                "separately in 2020 and re-combined in 2021."
            ),
            "bt_jk_boundary_shift_2015_2017": (
                "Customer and generation allocation adjustments between Banten and DKI Jakarta "
                "across 2015-2017 are retained as reported per official BPS footnotes."
            ),
            "missing_year_2016": (
                "BPS did not publish annual statistics for 2016; preserved as missing_source_year "
                "in canonical masters and linearly interpolated only in modeling history."
            ),
        },
        "uncertainty_calibration_k3": {
            "method": "K-3 Empirical Shifted-Log Horizon Uncertainty Calibration",
            "log_shift_gwh": 10.0,
            "size_buckets": ["small", "medium", "large"],
            "filtering_rules": (
                "Excludes origin-target pairs crossing the 2021 structural break and excludes "
                "bucket-migrating pairs."
            ),
            "horizon_extrapolation": (
                "Monotonic sub-linear scaling from observed h=1..3 quantiles to h=4..6."
            ),
            "national_q95_suppression": (
                "National q95 intervals are explicitly suppressed (NaN / insufficient_sample_size) "
                "because n=4 recursive origins < 10 minimum sample requirement."
            ),
            "regional_uncertainty_display_allowed": config.regional_uncertainty_display_allowed,
            "ui_policy": (
                "Regional prediction intervals are computed in forecasting uncertainty calibration "
                "artifacts and suppressed from production dashboard publication."
            ),
        },
        "contract_clarifications": {
            "legacy_ridge_used": {
                "value": config.legacy_model_reused,
                "meaning": (
                    "False certifies that the pre-project legacy raw-level Ridge regression "
                    "baseline is NOT reused. This flag is distinct from Supply V2 FWL slope "
                    "Ridge regularization (ridge_lambda=25.0) in national_reconciled_supply."
                ),
            },
            "national_yoy_basis": {
                "method": "matched_complete_regions",
                "description": (
                    "YoY national growth compares identical complete-region sets between t-1 and t "
                    "(common_regions = complete(t) ∩ complete(t-1)), preventing membership shifts "
                    "(31->33->34->33->34) from distorting growth rates."
                ),
            },
        },
        "geography": config.modeling_geography,
        "accounting_disclaimer": config.accounting_disclaimer,
    }


def frontend_metadata(
    config: DashboardConfig,
    *,
    models: pd.DataFrame | None = None,
    forecast_config: ProductionConfig | None = None,
) -> tuple[list[dict[str, str]], dict[str, str]]:
    """Build dynamic human-readable metadata list and string-only metadata_v2 dictionary."""
    fc_cfg = forecast_config if forecast_config is not None else _default_forecast_config()
    demand_info = _resolve_model_info("demand", models, fc_cfg)
    supply_info = _resolve_model_info("supply", models, fc_cfg)

    rolling_targets = (
        _format_year_span(fc_cfg.one_step_target_years) if fc_cfg is not None else "2019-2024"
    )
    recursive_origins = (
        _format_year_span(fc_cfg.recursive_origins) if fc_cfg is not None else "2018-2021"
    )
    recursive_max_horizon = int(fc_cfg.recursive_max_horizon) if fc_cfg is not None else 3

    supply_params = supply_info.get("params")
    if supply_info["active_model"] == "national_reconciled_supply" and supply_params:
        supply_desc = (
            f"Local generation menggunakan model produksi {supply_info['model_label']} "
            f"({supply_info['model_id']}), memadukan Drift nasional mulai "
            f"{supply_params['national_start_year']} dengan rekonsiliasi proporsional terhadap "
            f"step_intervention_damped regional (break_year={supply_params['break_year']}, "
            f"ridge_lambda={supply_params['ridge_lambda']}, damping_phi={supply_params['damping_phi']})."
        )
    else:
        supply_desc = (
            f"Local generation menggunakan model produksi {supply_info['model_label']} "
            f"({supply_info['model_id']})."
        )

    metadata = [
        {
            "bagian": "Cakupan",
            "penjelasan": (
                f"Dashboard menggunakan {config.expected_regions} wilayah modeling harmonisasi "
                f"untuk periode {config.history_start_year}-{config.forecast_end_year}."
            ),
        },
        {
            "bagian": "Demand",
            "penjelasan": (
                f"Distributed electricity menggunakan model produksi {demand_info['model_label']} "
                f"({demand_info['model_id']}; dievaluasi terhadap {demand_info['evaluated_backtest_model_count']} "
                "model backtest produksi, peringkat #1 dari 12 kandidat Fase 2)."
            ),
        },
        {
            "bagian": "Supply",
            "penjelasan": supply_desc,
        },
        {
            "bagian": "Benchmark",
            "penjelasan": (
                f"Benchmark Fase 2 mengevaluasi 26 model (14 supply, 12 demand); backtest produksi "
                f"menguji {supply_info['evaluated_backtest_model_count']} model supply dan "
                f"{demand_info['evaluated_backtest_model_count']} model demand."
            ),
        },
        {
            "bagian": "Validasi",
            "penjelasan": (
                f"Rolling one-step {rolling_targets} dan recursive multi-step origins "
                f"{recursive_origins}, horizon maksimum {recursive_max_horizon}."
            ),
        },
        {
            "bagian": "Ketidakpastian",
            "penjelasan": (
                "Kalibrasi K-3 memakai log-residual tergeser (LOG_SHIFT_GWH=10.0), menyaring "
                "pasangan lintas break 2021, dan mensupresi q95 nasional (n=4 < 10); interval "
                "regional tidak dipublikasikan di UI."
            ),
        },
        {
            "bagian": "Tata Kelola ADR-001",
            "penjelasan": (
                "Master historis 2011-2024 dibekukan sesuai CSV BPS (510 sel diaudit PDF), "
                "mencatat break STPL 2021 + cross-check ESDM serta anomali KR 2020 (PT PLN Batam)."
            ),
        },
        {
            "bagian": "YoY Nasional",
            "penjelasan": (
                "Pertumbuhan YoY nasional dihitung atas irisan wilayah lengkap antar tahun berurutan "
                "(common_regions = complete(t) ∩ complete(t-1)) untuk menghindari distorsi keanggotaan."
            ),
        },
        {
            "bagian": "Kualitas",
            "penjelasan": "Tahun 2016 diinterpolasi hanya pada modeling layer; missing lain tetap eksplisit.",
        },
        {
            "bagian": "Klarifikasi Ridge",
            "penjelasan": (
                "legacy_ridge_used=false menandakan model Ridge raw-level lama pra-proyek tidak dipakai; "
                "berbeda dari Ridge slope damping (lambda=25.0) pada Supply V2."
            ),
        },
        {
            "bagian": "Penduduk",
            "penjelasan": "Population dan per-capita masih backlog dan ditampilkan sebagai N/A.",
        },
        {
            "bagian": "RUPTL",
            "penjelasan": "RUPTL digunakan sebagai benchmark/scenario, bukan target forecast produksi.",
        },
        {
            "bagian": "Akuntansi",
            "penjelasan": config.accounting_disclaimer,
        },
    ]

    metadata_v2: dict[str, str] = {
        "stage_version": config.source_dashboard_stage,
        "schema_version": config.schema_version,
        "period": f"{config.history_start_year}-{config.forecast_end_year}",
        "region_count": str(config.expected_regions),
        "forecast_start": str(config.forecast_start_year),
        "forecast_end": str(config.forecast_end_year),
        "demand_model": str(demand_info["model_id"]),
        "supply_model": str(supply_info["model_id"]),
        "demand_active_model": str(demand_info["active_model"]),
        "supply_active_model": str(supply_info["active_model"]),
        "demand_model_label": str(demand_info["model_label"]),
        "supply_model_label": str(supply_info["model_label"]),
        "demand_evaluated_models": str(demand_info["evaluated_backtest_model_count"]),
        "supply_evaluated_models": str(supply_info["evaluated_backtest_model_count"]),
        "population_status": "backlog_not_integrated",
        "ruptl_role": "benchmark_scenario_only",
        "regional_uncertainty": (
            "published" if config.regional_uncertainty_display_allowed else "not_published"
        ),
        "accounting_interpretation": "not_shortage_surplus_or_adequacy",
        "legacy_ridge_clarification": (
            "legacy_raw_level_ridge_not_reused_distinct_from_v2_fwl_slope_damping"
        ),
        "national_yoy_method": "matched_complete_regions",
        "adr_reference": "ADR-001",
        "uncertainty_calibration_method": "K-3_shifted_log_national_q95_suppressed",
        "benchmark_summary": "26_models_evaluated_14_supply_12_demand",
    }
    if supply_params:
        metadata_v2["supply_break_year"] = str(supply_params["break_year"])
        metadata_v2["supply_ridge_lambda"] = str(supply_params["ridge_lambda"])
        metadata_v2["supply_damping_phi"] = str(supply_params["damping_phi"])
        metadata_v2["supply_national_start_year"] = str(supply_params["national_start_year"])

    return metadata, metadata_v2
