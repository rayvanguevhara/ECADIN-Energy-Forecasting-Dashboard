from __future__ import annotations

import pandas as pd

from ecadin_energy.forecasting.configuration import ProductionConfig
from ecadin_energy.forecasting.exceptions import ContractError


def validate_modeling_panel(
    panel: pd.DataFrame,
    config: ProductionConfig,
    *,
    domain: str,
) -> dict[str, object]:
    required = {
        "domain",
        "region_id",
        "region_name",
        "year",
        "actual_gwh",
        "training_gwh",
        "target_status",
        "training_eligible",
        "validation_eligible",
    }
    missing = sorted(required - set(panel.columns))
    failures: list[str] = []
    if missing:
        failures.append(f"missing columns: {missing}")

    expected_rows = config.expected_regions * len(config.historical_years)
    if len(panel) != expected_rows:
        failures.append(
            f"expected {expected_rows} rows, found {len(panel)}"
        )
    if panel["region_id"].nunique() != config.expected_regions:
        failures.append(
            f"expected {config.expected_regions} regions, found "
            f"{panel['region_id'].nunique()}"
        )
    if sorted(panel["year"].unique().tolist()) != list(
        config.historical_years
    ):
        failures.append("historical year coverage mismatch")
    if panel.duplicated(["region_id", "year"]).any():
        failures.append("duplicate region-year key")
    if not panel["domain"].eq(domain).all():
        failures.append("domain column mismatch")

    interpolation_rows = panel.loc[
        panel["year"].isin(config.missing_data.interpolate_years)
        & panel["is_interpolated_target"]
    ]
    expected_interpolated = (
        config.expected_regions * len(config.missing_data.interpolate_years)
    )
    if len(interpolation_rows) != expected_interpolated:
        failures.append(
            f"expected {expected_interpolated} selected-year interpolations, "
            f"found {len(interpolation_rows)}"
        )
    pre_break = panel.loc[
        panel["region_id"].isin(
            config.missing_data.exclude_pre_year_regions
        )
        & panel["year"].lt(config.missing_data.exclude_before_year)
    ]
    if pre_break["training_gwh"].notna().any():
        failures.append("pre-boundary geography rows entered training")
    if failures:
        raise ContractError(
            f"{domain} modeling panel contract failed: "
            + " | ".join(failures)
        )

    return {
        "domain": domain,
        "rows": len(panel),
        "regions": panel["region_id"].nunique(),
        "years": (
            int(panel["year"].min()),
            int(panel["year"].max()),
        ),
        "training_rows": int(panel["training_eligible"].sum()),
        "validation_rows": int(panel["validation_eligible"].sum()),
        "interpolated_rows": int(
            panel["is_interpolated_target"].sum()
        ),
        "excluded_geography_rows": int(
            panel["target_status"].eq(
                "excluded_geography_break"
            ).sum()
        ),
    }
