from __future__ import annotations

from ecadin_energy.forecasting.models.drift import DriftModel


class SupplyDriftV1Model(DriftModel):
    """Production supply Drift model with empirical uncertainty calibration."""

    model_id = "supply_production_drift_v1"
    model_label = "Drift"
