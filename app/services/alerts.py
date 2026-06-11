"""Alert center — turns drift/prediction into actionable, deduplicated alerts."""

from __future__ import annotations

import time
import uuid
from collections import deque
from dataclasses import asdict, dataclass, field
from threading import RLock
from typing import Deque, Dict, List, Optional

from ..config import CONFIG
from ..subsystems.base import TelemetrySample


@dataclass
class Alert:
    id: str
    vehicle_id: str
    severity: str            # "warn" | "critical"
    title: str
    detail: str
    drift_score: float
    failure_probability: float
    ci_low: float
    ci_high: float
    time_to_failure_hours: Optional[float]
    scenario: str
    created_at: float
    acknowledged: bool = False


class AlertCenter:
    def __init__(self, capacity: int = 500) -> None:
        self._lock = RLock()
        self._alerts: Deque[Alert] = deque(maxlen=capacity)
        # Dedup: at most one open alert per (vehicle, severity)
        self._open_index: Dict[str, str] = {}  # f"{vid}:{sev}" -> alert_id

    def evaluate(
        self,
        vehicle_id: str,
        drift: float,
        prediction: Dict[str, float],
        sample: TelemetrySample,
    ) -> Optional[Alert]:
        p = prediction.get("probability", 0.0)
        severity: Optional[str] = None
        if p >= CONFIG.failure_critical_prob or drift >= CONFIG.drift_critical_score:
            severity = "critical"
        elif p >= CONFIG.failure_warn_prob or drift >= CONFIG.drift_warn_score:
            severity = "warn"
        if severity is None:
            return None
        key = f"{vehicle_id}:{severity}"
        if key in self._open_index:
            return None  # already alerted
        alert = Alert(
            id=str(uuid.uuid4())[:8],
            vehicle_id=vehicle_id,
            severity=severity,
            title=self._title(severity, sample.scenario),
            detail=self._detail(drift, prediction, sample),
            drift_score=round(drift, 3),
            failure_probability=p,
            ci_low=prediction.get("ci_low", 0.0),
            ci_high=prediction.get("ci_high", 0.0),
            time_to_failure_hours=prediction.get("time_to_failure_hours"),
            scenario=sample.scenario,
            created_at=time.time(),
        )
        with self._lock:
            self._alerts.appendleft(alert)
            self._open_index[key] = alert.id
        return alert

    def list(self, limit: int = 50) -> List[Dict[str, object]]:
        with self._lock:
            return [asdict(a) for a in list(self._alerts)[:limit]]

    def acknowledge(self, alert_id: str) -> bool:
        with self._lock:
            for a in self._alerts:
                if a.id == alert_id:
                    a.acknowledged = True
                    # free dedup slot so a new alert can fire if condition reoccurs
                    key = f"{a.vehicle_id}:{a.severity}"
                    self._open_index.pop(key, None)
                    return True
            return False

    def count_open(self) -> int:
        with self._lock:
            return sum(1 for a in self._alerts if not a.acknowledged)

    def clear(self) -> None:
        with self._lock:
            self._alerts.clear()
            self._open_index.clear()

    @staticmethod
    def _title(severity: str, scenario: str) -> str:
        scen_text = {
            "coolant_pump_degrading": "Coolant pump degradation",
            "cell_imbalance": "Cell imbalance trending up",
            "sensor_bias": "Sensor bias suspected",
            "nominal": "Anomalous thermal behaviour",
        }.get(scenario, "Anomalous thermal behaviour")
        prefix = "CRITICAL" if severity == "critical" else "WARNING"
        return f"{prefix}: {scen_text}"

    @staticmethod
    def _detail(drift: float, prediction: Dict[str, float], sample: TelemetrySample) -> str:
        p = prediction.get("probability", 0.0)
        ttf = prediction.get("time_to_failure_hours")
        return (
            f"Drift score {drift:.2f}; failure probability {p*100:.1f}% "
            f"(95% CI {prediction.get('ci_low', 0)*100:.1f}–"
            f"{prediction.get('ci_high', 0)*100:.1f}%); "
            f"estimated time-to-failure {ttf:.1f}h. "
            f"Latest max-cell {sample.actual.get('max_cell_temp_c')}°C, "
            f"coolant ΔT {sample.actual.get('coolant_delta_c')}°C."
        )
