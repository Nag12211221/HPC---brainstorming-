"""A/B testing harness — deterministic assignment + outcome tracking."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from threading import RLock
from typing import Dict, List

from ..config import CONFIG


@dataclass
class ArmStats:
    arm: str
    assigned: int = 0
    alerts_fired: int = 0
    true_positives: int = 0
    false_positives: int = 0
    missed: int = 0

    @property
    def precision(self) -> float:
        denom = self.true_positives + self.false_positives
        return round(self.true_positives / denom, 3) if denom else 0.0

    @property
    def recall(self) -> float:
        denom = self.true_positives + self.missed
        return round(self.true_positives / denom, 3) if denom else 0.0


class ABRouter:
    """Hash-based deterministic routing across configured model arms."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._stats: Dict[str, ArmStats] = {}

    def assign(self, vehicle_id: str) -> str:
        split = CONFIG.ab_traffic_split or {"ewma_plus_v2": 1.0}
        # deterministic bucketing in [0, 1)
        h = int(hashlib.md5(vehicle_id.encode()).hexdigest(), 16)
        bucket = (h % 10_000) / 10_000.0
        acc = 0.0
        chosen = list(split.keys())[-1]
        for arm, weight in split.items():
            acc += weight
            if bucket < acc:
                chosen = arm
                break
        with self._lock:
            st = self._stats.setdefault(chosen, ArmStats(arm=chosen))
            st.assigned += 1
        return chosen

    def record(self, arm: str, outcome: str) -> None:
        """outcome: alert | true_positive | false_positive | missed."""
        with self._lock:
            st = self._stats.setdefault(arm, ArmStats(arm=arm))
            if outcome == "alert":
                st.alerts_fired += 1
            elif outcome == "true_positive":
                st.true_positives += 1
            elif outcome == "false_positive":
                st.false_positives += 1
            elif outcome == "missed":
                st.missed += 1

    def report(self) -> List[Dict[str, object]]:
        with self._lock:
            out = []
            for st in self._stats.values():
                out.append({
                    "arm": st.arm,
                    "assigned": st.assigned,
                    "alerts_fired": st.alerts_fired,
                    "true_positives": st.true_positives,
                    "false_positives": st.false_positives,
                    "missed": st.missed,
                    "precision": st.precision,
                    "recall": st.recall,
                })
            return out


ab_router = ABRouter()
