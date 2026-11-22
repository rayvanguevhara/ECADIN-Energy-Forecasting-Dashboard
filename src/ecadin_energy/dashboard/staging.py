from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from ecadin_energy.dashboard.configuration import load_dashboard_config
from ecadin_energy.dashboard.data_quality import (
    build_quality_flags_highlights,
    build_quality_flags_summary,
    build_quality_review,
    build_quality_summary,
)
from ecadin_energy.dashboard.energy_map import build_map_timeseries
from ecadin_energy.dashboard.frontend_payload import build_frontend_payload
from ecadin_energy.dashboard.loaders import load_dashboard_inputs
from ecadin_energy.dashboard.methodology import build_methodology
from ecadin_energy.dashboard.national_overview import build_national_timeseries
from ecadin_energy.dashboard.production_models import build_model_summary
from ecadin_energy.dashboard.region_detail import build_region_detail
from ecadin_energy.dashboard.regional_ranking import build_regional_ranking
from ecadin_energy.dashboard.serializers import sha256_file, write_csv, write_json
from ecadin_energy.forecasting.configuration import ProductionConfig, load_production_config


DETERMINISTIC_DATA_FILES = (
    "dashboard_province_detail.csv",
    "dashboard_national_timeseries.csv",
    "dashboard_map_timeseries.csv",
    "dashboard_regional_ranking.csv",
    "dashboard_model_summary.csv",
    "dashboard_data_quality_summary.csv",
    "dashboard_data_quality_review.csv",
    "dashboard_data_quality_flags_summary.csv",
    "dashboard_methodology.json",
    "dashboard_source_registry.json",
    "dashboard-production.json",
    "dashboard_input_hashes.csv",
)

OUTPUT_HASH_MANIFEST_FILE = "dashboard_output_hashes.csv"

DETERMINISTIC_FILES = DETERMINISTIC_DATA_FILES + (OUTPUT_HASH_MANIFEST_FILE,)


def build_dashboard_staging(
    *,
    project_root: str | Path | None = None,
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    """Build all deterministic dashboard staging tables, payload, and SHA-256 manifests."""
    config = load_dashboard_config(config_path, project_root=project_root)
    paths = config.paths(project_root)
    inputs = load_dashboard_inputs(paths.root)

    forecast_cfg_path = paths.root / "configs/forecasting/production.json"
    forecast_config: ProductionConfig | None = (
        load_production_config(forecast_cfg_path, project_root=paths.root)
        if forecast_cfg_path.is_file()
        else None
    )

    detail = build_region_detail(inputs["combined"], inputs["regions"], config)
    national = build_national_timeseries(detail, config.expected_regions)
    map_frame = build_map_timeseries(detail)
    ranking = build_regional_ranking(detail)
    models = build_model_summary(
        inputs["models"],
        config,
        forecast_config=forecast_config,
    )
    quality_summary = build_quality_summary(detail)
    quality_review = build_quality_review(detail)
    quality_flags_summary = build_quality_flags_summary(inputs["quality_flags"])
    quality_flags_highlights = build_quality_flags_highlights(
        inputs["quality_flags"],
        inputs["regions"],
    )
    methodology = build_methodology(
        config,
        models=models,
        forecast_config=forecast_config,
    )

    input_paths = [
        inputs["combined_path"],
        inputs["model_path"],
        inputs["regions_path"],
        inputs["quality_path"],
        inputs["contract_path"],
    ]
    input_hash_rows = pd.DataFrame(
        [
            {
                "source_id": path.stem,
                "relative_path": path.relative_to(paths.root).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in input_paths
        ]
    )
    source_hashes = {
        row["relative_path"]: row["sha256"]
        for row in input_hash_rows.to_dict(orient="records")
    }
    payload = build_frontend_payload(
        detail,
        national,
        models,
        source_hashes,
        config,
        forecast_config=forecast_config,
        quality_flags=inputs["quality_flags"],
        quality_flags_summary=quality_flags_summary,
        quality_flags_highlights=quality_flags_highlights,
        methodology=methodology,
    )

    paths.staging.mkdir(parents=True, exist_ok=True)
    write_csv(detail, paths.staging / "dashboard_province_detail.csv")
    write_csv(national, paths.staging / "dashboard_national_timeseries.csv")
    write_csv(map_frame, paths.staging / "dashboard_map_timeseries.csv")
    write_csv(ranking, paths.staging / "dashboard_regional_ranking.csv")
    write_csv(models, paths.staging / "dashboard_model_summary.csv")
    write_csv(quality_summary, paths.staging / "dashboard_data_quality_summary.csv")
    write_csv(quality_review, paths.staging / "dashboard_data_quality_review.csv")
    write_csv(
        quality_flags_summary,
        paths.staging / "dashboard_data_quality_flags_summary.csv",
    )
    write_json(methodology, paths.staging / "dashboard_methodology.json")
    write_json(payload, paths.staging / "dashboard-production.json")
    write_csv(input_hash_rows, paths.staging / "dashboard_input_hashes.csv")

    payload_sha256 = sha256_file(paths.staging / "dashboard-production.json")
    registry = {
        "schema_version": "dashboard_source_registry_v1",
        "status": "production",
        "production_ready": True,
        "source_dashboard_stage": config.source_dashboard_stage,
        "source_hashes": source_hashes,
        "payload_relative_path": "dashboard-production.json",
        "payload_sha256": payload_sha256,
        "canonical_master_modified": False,
        "frontend_source_modified": False,
        "population_status": "backlog_not_integrated",
        "ruptl_role": "benchmark_scenario_only",
        "accounting_disclaimer": config.accounting_disclaimer,
    }
    write_json(registry, paths.staging / "dashboard_source_registry.json")

    output_hash_rows = pd.DataFrame(
        [
            {
                "artifact_id": Path(name).stem,
                "relative_path": name,
                "size_bytes": (paths.staging / name).stat().st_size,
                "sha256": sha256_file(paths.staging / name),
            }
            for name in DETERMINISTIC_DATA_FILES
        ]
    )
    write_csv(output_hash_rows, paths.staging / OUTPUT_HASH_MANIFEST_FILE)

    deterministic_hashes = {
        name: sha256_file(paths.staging / name) for name in DETERMINISTIC_FILES
    }
    summary = {
        "schema_version": "dashboard_staging_summary_v1",
        "status": "completed",
        "processed_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "region_rows": int(len(detail)),
        "national_rows": int(len(national)),
        "regions": int(detail["region_id"].nunique()),
        "years": [int(detail["year"].min()), int(detail["year"].max())],
        "complete_pairs": int(detail["available"].sum()),
        "historical_incomplete_pairs": int(
            (detail["data_type"].eq("historical") & ~detail["available"]).sum()
        ),
        "forecast_incomplete_pairs": int(
            (detail["data_type"].eq("forecast") & ~detail["available"]).sum()
        ),
        "quality_flags_total": int(len(inputs["quality_flags"])),
        "canonical_master_modified": False,
        "frontend_source_modified": False,
        "deterministic_output_hashes": deterministic_hashes,
    }
    write_json(summary, paths.staging / "dashboard_staging_summary.json")
    return {
        "config": config,
        "paths": paths,
        "summary": summary,
        "detail": detail,
        "national": national,
        "models": models,
    }
