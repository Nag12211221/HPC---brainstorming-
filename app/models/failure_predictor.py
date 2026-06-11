"""Failure probability + time-to-failure estimation.

We deliberately use a transparent logistic-style model so the dashboard can
explain *why* a vehicle is flagged. Two model versions are bundled so the
A/B testing harness has something real to compare.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Tuple


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


@dataclass
class FailureModel:
    """Logistic model with named coefficients (interpretable for the UI)."""

    version: str
    description: str
    # weight per feature; missing features default to 0
    weights: Dict[str, float]
    bias: float
    # variance proxy used to derive a confidence interval on probability
    epistemic_sigma: float = 0.08

    def predict(self, features: Dict[str, float], drift_score: float) -> Dict[str, float]:
        z = self.bias + drift_score * self.weights.get("__drift__", 0.0)
        for k, w in self.weights.items():
            if k == "__drift__":
                continue
            z += w * features.get(k, 0.0)
        p = _sigmoid(z)

        # Confidence interval — propagate sigma through the logit
        z_lo = z - 1.96 * self.epistemic_sigma * max(1.0, abs(z))
        z_hi = z + 1.96 * self.epistemic_sigma * max(1.0, abs(z))
        ci_lo = _sigmoid(z_lo)
        ci_hi = _sigmoid(z_hi)

        # Time-to-failure: heuristic — high prob & rising residual ⇒ short horizon
        slope_signal = abs(features.get("residual_slope_max_cell_temp_c", 0.0)) + \
                       abs(features.get("residual_slope_coolant_delta_c", 0.0))
        # base horizon shrinks from ~72h at p=0.1 to ~2h at p=0.9
        base_hours = max(2.0, 72.0 * (1.0 - p) ** 2)
        if slope_signal > 0.05:
            base_hours = base_hours / (1.0 + slope_signal * 3.0)
        ttf_hours = max(0.5, base_hours)

        return {
            "probability": round(p, 4),
            "ci_low": round(ci_lo, 4),
            "ci_high": round(ci_hi, 4),
            "logit": round(z, 4),
            "time_to_failure_hours": round(ttf_hours, 2),
            "model_version": self.version,
        }


# --- Pre-defined model registry (also used by the A/B harness) -----------

_BASELINE_V1 = FailureModel(
    version="baseline_v1",
    description="Threshold-aware logistic over residual means + drift score.",
    weights={
        "__drift__": 2.2,
        "residual_mean_max_cell_temp_c": 0.35,
        "residual_mean_coolant_delta_c": 0.30,
        "residual_mean_coolant_flow_lpm": -0.40,
    },
    bias=-2.5,
    epistemic_sigma=0.12,
)

_EWMA_PLUS_V2 = FailureModel(
    version="ewma_plus_v2",
    description="Adds residual-slope features for earlier drift response.",
    weights={
        "__drift__": 2.6,
        "residual_mean_max_cell_temp_c": 0.30,
        "residual_mean_coolant_delta_c": 0.32,
        "residual_mean_coolant_flow_lpm": -0.45,
        "residual_slope_max_cell_temp_c": 6.0,
        "residual_slope_coolant_delta_c": 5.0,
        "residual_slope_coolant_flow_lpm": -7.0,
    },
    bias=-2.9,
    epistemic_sigma=0.07,
)


class FailureModelRegistry:
    """Versioned model registry exposed through the API."""

    def __init__(self) -> None:
        self._models: Dict[str, FailureModel] = {}
        self._history: List[Tuple[str, str]] = []  # (version, description)
        self.register(_BASELINE_V1)
        self.register(_EWMA_PLUS_V2)
        self._active = "ewma_plus_v2"

    def register(self, model: FailureModel) -> None:
        self._models[model.version] = model
        self._history.append((model.version, model.description))

    def get(self, version: str) -> FailureModel:
        return self._models[version]

    def active(self) -> FailureModel:
        return self._models[self._active]

    def set_active(self, version: str) -> None:
        if version not in self._models:
            raise KeyError(version)
        self._active = version

    def list(self) -> List[Dict[str, str]]:
        return [
            {
                "version": v,
                "description": m.description,
                "active": v == self._active,
            }
            for v, m in self._models.items()
        ]

    def history(self) -> List[Dict[str, str]]:
        return [{"version": v, "description": d} for v, d in self._history]


model_registry = FailureModelRegistry()
