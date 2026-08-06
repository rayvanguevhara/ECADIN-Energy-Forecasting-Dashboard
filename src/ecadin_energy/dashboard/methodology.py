from __future__ import annotations

from ecadin_energy.dashboard.configuration import DashboardConfig


def build_methodology(config: DashboardConfig) -> dict[str, object]:
    return {
        "schema_version": "dashboard_methodology_v1",
        "definitions": {
            "demand": "Annual distributed electricity within a harmonized modeling region (GWh).",
            "supply": "Annual local electricity generation within the same harmonized region (GWh).",
            "accounting_difference": "Local generation minus distributed electricity.",
        },
        "production_models": {
            "demand": "Drift",
            "supply": "Drift V1",
            "frequency": "annual",
            "historical_period": f"{config.history_start_year}-{config.history_end_year}",
            "forecast_period": f"{config.forecast_start_year}-{config.forecast_end_year}",
        },
        "validation": {
            "rolling_one_step_targets": "2019-2024",
            "recursive_origins": "2018-2021",
            "recursive_max_horizon": 3,
            "metrics": [
                "macro_sMAPE", "macro_MASE", "micro_RMSE", "aggregate_bias",
                "challenger_win_rate_vs_Drift",
            ],
        },
        "data_treatment": {
            "year_2016": "Interpolated in modeling history only; not an observed validation target.",
            "other_missing": "Preserved as missing; never converted to zero.",
            "population": "Backlog; not integrated into the production dashboard data contract.",
            "ruptl": "Benchmark and scenario reference only; not a production target.",
        },
        "geography": config.modeling_geography,
        "accounting_disclaimer": config.accounting_disclaimer,
    }


def frontend_metadata(config: DashboardConfig) -> tuple[list[dict[str, str]], dict[str, str]]:
    metadata = [
        {"bagian": "Cakupan", "penjelasan": f"Dashboard menggunakan {config.expected_regions} wilayah modeling harmonisasi untuk periode {config.history_start_year}-{config.forecast_end_year}."},
        {"bagian": "Demand", "penjelasan": "Distributed electricity menggunakan model produksi Drift."},
        {"bagian": "Supply", "penjelasan": "Local generation menggunakan model produksi Drift V1."},
        {"bagian": "Validasi", "penjelasan": "Rolling one-step 2019-2024 dan recursive multi-step origins 2018-2021, horizon maksimum 3."},
        {"bagian": "Kualitas", "penjelasan": "Tahun 2016 diinterpolasi hanya pada modeling layer; missing lain tetap eksplisit."},
        {"bagian": "Penduduk", "penjelasan": "Population dan per-capita masih backlog dan ditampilkan sebagai N/A."},
        {"bagian": "RUPTL", "penjelasan": "RUPTL digunakan sebagai benchmark/scenario, bukan target forecast produksi."},
        {"bagian": "Akuntansi", "penjelasan": config.accounting_disclaimer},
    ]
    metadata_v2 = {
        "stage_version": config.source_dashboard_stage,
        "schema_version": config.schema_version,
        "period": f"{config.history_start_year}-{config.forecast_end_year}",
        "region_count": str(config.expected_regions),
        "forecast_start": str(config.forecast_start_year),
        "forecast_end": str(config.forecast_end_year),
        "demand_model": "demand_production_drift",
        "supply_model": "supply_production_drift_v1",
        "population_status": "backlog_not_integrated",
        "ruptl_role": "benchmark_scenario_only",
        "regional_uncertainty": "not_published",
        "accounting_interpretation": "not_shortage_surplus_or_adequacy",
    }
    return metadata, metadata_v2
