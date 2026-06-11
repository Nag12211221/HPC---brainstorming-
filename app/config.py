"""Platform-wide configuration with sensible defaults for the POC."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class PlatformConfig:
    """Mutable configuration container exposed through the /api/config endpoint."""

    # Fleet simulation
    fleet_size: int = 25
    tick_seconds: float = 1.0  # simulated seconds advanced per refresh tick

    # Battery thermal nominal envelope (deg C / A / V)
    cell_temp_nominal_c: float = 32.0
    cell_temp_warn_c: float = 48.0
    cell_temp_critical_c: float = 58.0
    coolant_delta_warn_c: float = 8.0
    coolant_delta_critical_c: float = 14.0

    # Drift detector (EWMA)
    drift_alpha: float = 0.15           # smoothing factor
    drift_warn_score: float = 0.45      # |score| triggers WARN
    drift_critical_score: float = 0.75  # |score| triggers CRITICAL

    # Failure model
    failure_warn_prob: float = 0.35
    failure_critical_prob: float = 0.65
    confidence_z: float = 1.96  # 95% CI

    # ROI assumptions (USD)
    avg_warranty_claim_usd: float = 4200.0
    annual_claims_per_1k_vehicles: int = 38
    validation_cycle_cost_usd: float = 1_250_000.0
    validation_cycle_reduction_pct: float = 0.35  # 35% target
    early_detection_recovery_pct: float = 0.62    # claims avoided when caught early

    # A/B testing default split
    ab_traffic_split: Dict[str, float] = field(
        default_factory=lambda: {"baseline_v1": 0.5, "ewma_plus_v2": 0.5}
    )

    def as_dict(self) -> Dict[str, object]:
        d = self.__dict__.copy()
        d["ab_traffic_split"] = dict(self.ab_traffic_split)
        return d

    def update(self, patch: Dict[str, object]) -> Dict[str, object]:
        """Apply a partial update and return the new state."""
        for key, value in patch.items():
            if not hasattr(self, key):
                raise KeyError(f"Unknown config key: {key}")
            current = getattr(self, key)
            if isinstance(current, dict) and isinstance(value, dict):
                current.update(value)
            else:
                setattr(self, key, type(current)(value) if current is not None else value)
        return self.as_dict()


CONFIG = PlatformConfig()
