"""ROI calculator — translates detection quality into warranty savings."""

from __future__ import annotations

from typing import Dict

from ..config import CONFIG


def compute_roi(fleet_size: int, detection_lift_pct: float = 0.0) -> Dict[str, float]:
    """Compute projected warranty savings.

    ``detection_lift_pct`` represents additional early-detection rate enabled by
    the platform on top of the configured baseline.
    """
    cfg = CONFIG
    claims_baseline = fleet_size / 1000.0 * cfg.annual_claims_per_1k_vehicles
    cost_baseline = claims_baseline * cfg.avg_warranty_claim_usd

    recovery = min(0.95, cfg.early_detection_recovery_pct + detection_lift_pct)
    claims_avoided = claims_baseline * recovery
    cost_with_platform = cost_baseline - claims_avoided * cfg.avg_warranty_claim_usd
    warranty_savings = cost_baseline - cost_with_platform

    val_savings = cfg.validation_cycle_cost_usd * cfg.validation_cycle_reduction_pct

    return {
        "fleet_size": fleet_size,
        "annual_claims_baseline": round(claims_baseline, 1),
        "annual_claims_avoided": round(claims_avoided, 1),
        "baseline_warranty_cost_usd": round(cost_baseline, 2),
        "projected_warranty_cost_usd": round(cost_with_platform, 2),
        "annual_warranty_savings_usd": round(warranty_savings, 2),
        "validation_cycle_savings_usd": round(val_savings, 2),
        "total_annual_savings_usd": round(warranty_savings + val_savings, 2),
        "validation_cycle_reduction_pct": cfg.validation_cycle_reduction_pct,
        "early_detection_rate": round(recovery, 3),
        "avg_claim_cost_usd": cfg.avg_warranty_claim_usd,
    }
