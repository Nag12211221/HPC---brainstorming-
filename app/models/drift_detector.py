"""EWMA-based drift detector with a normalised score in roughly [-1, 1+]."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class DriftState:
    ewma: Dict[str, float] = field(default_factory=dict)
    ewvar: Dict[str, float] = field(default_factory=dict)


class DriftDetector:
    """Tracks per-feature EWMA mean/variance and produces a normalised drift score.

    The score combines the magnitude of recent residuals with the slope of the
    residual trend. Values >0.45 are treated as WARN, >0.75 as CRITICAL.
    """

    def __init__(self, alpha: float = 0.15) -> None:
        self.alpha = alpha
        self._states: Dict[str, DriftState] = {}

    def update(self, vehicle_id: str, features: Dict[str, float]) -> Dict[str, float]:
        st = self._states.setdefault(vehicle_id, DriftState())
        score = 0.0
        contributions: Dict[str, float] = {}
        for key, value in features.items():
            prev_mean = st.ewma.get(key, value)
            prev_var = st.ewvar.get(key, 1.0)
            mean = (1 - self.alpha) * prev_mean + self.alpha * value
            var = (1 - self.alpha) * (prev_var + self.alpha * (value - prev_mean) ** 2)
            st.ewma[key] = mean
            st.ewvar[key] = max(var, 1e-3)

            if key.startswith("residual_mean_"):
                contributions[key] = abs(mean) / 3.0  # 3°C residual ≈ 1.0
                score += contributions[key]
            elif key.startswith("residual_slope_"):
                contributions[key] = abs(mean) * 4.0
                score += contributions[key]

        # average across residual channels for stability
        n_resid = max(1, sum(1 for k in features if k.startswith("residual_")))
        score = score / n_resid
        return {"score": round(score, 4), "contributions": contributions}

    def reset(self, vehicle_id: str) -> None:
        self._states.pop(vehicle_id, None)
