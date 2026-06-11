"""Fleet simulator — keeps rolling telemetry per vehicle and runs models."""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional

from ..config import CONFIG
from ..models.drift_detector import DriftDetector
from ..models.failure_predictor import FailureModel, model_registry
from ..subsystems.base import Subsystem, TelemetrySample
from .ab_testing import ab_router
from .alerts import AlertCenter

logger = logging.getLogger(__name__)


@dataclass
class VehicleState:
    vehicle_id: str
    region: str
    model_year: int
    samples: Deque[TelemetrySample] = field(default_factory=lambda: deque(maxlen=600))
    last_drift: float = 0.0
    last_prediction: Dict[str, float] = field(default_factory=dict)
    assigned_model: str = "ewma_plus_v2"
    last_scenario: str = "nominal"


class FleetManager:
    """Holds per-vehicle simulation state and orchestrates model inference."""

    REGIONS = ["NA-West", "NA-East", "EU-DE", "EU-UK", "APAC-JP", "APAC-CN"]

    def __init__(self, subsystem: Subsystem) -> None:
        self.subsystem = subsystem
        self.vehicles: Dict[str, VehicleState] = {}
        self.drift = DriftDetector(alpha=CONFIG.drift_alpha)
        self.alerts = AlertCenter()
        self._lock = threading.RLock()
        self._init_fleet(CONFIG.fleet_size)
        # background ticker
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    # -- Public API -------------------------------------------------------

    def list_vehicles(self) -> List[Dict[str, object]]:
        with self._lock:
            out = []
            for v in self.vehicles.values():
                pred = v.last_prediction or {}
                out.append({
                    "vehicle_id": v.vehicle_id,
                    "region": v.region,
                    "model_year": v.model_year,
                    "drift_score": v.last_drift,
                    "failure_probability": pred.get("probability", 0.0),
                    "ci_low": pred.get("ci_low", 0.0),
                    "ci_high": pred.get("ci_high", 0.0),
                    "time_to_failure_hours": pred.get("time_to_failure_hours"),
                    "status": self._status(v.last_drift, pred.get("probability", 0.0)),
                    "assigned_model": v.assigned_model,
                    "scenario": v.last_scenario,
                })
            return out

    def get_vehicle(self, vehicle_id: str, window: int = 180) -> Optional[Dict[str, object]]:
        with self._lock:
            v = self.vehicles.get(vehicle_id)
            if v is None:
                return None
            samples = list(v.samples)[-window:]
            timeline = [
                {
                    "t": s.t,
                    "actual": s.actual,
                    "expected": s.expected,
                    "fault_active": s.fault_active,
                    "scenario": s.scenario,
                }
                for s in samples
            ]
            return {
                "vehicle_id": v.vehicle_id,
                "region": v.region,
                "model_year": v.model_year,
                "assigned_model": v.assigned_model,
                "drift_score": v.last_drift,
                "prediction": v.last_prediction,
                "scenario": v.last_scenario,
                "timeline": timeline,
                "signals": self.subsystem.signals,
                "units": self.subsystem.units,
            }

    def reseed(self, fleet_size: Optional[int] = None) -> None:
        with self._lock:
            self.vehicles.clear()
            self.alerts.clear()
            self._init_fleet(fleet_size or CONFIG.fleet_size)

    def stop(self) -> None:
        self._stop.set()

    def summary(self) -> Dict[str, object]:
        with self._lock:
            statuses = {"healthy": 0, "watch": 0, "warn": 0, "critical": 0}
            tot_p = 0.0
            for v in self.vehicles.values():
                p = (v.last_prediction or {}).get("probability", 0.0)
                statuses[self._status(v.last_drift, p)] += 1
                tot_p += p
            n = max(1, len(self.vehicles))
            return {
                "fleet_size": len(self.vehicles),
                "avg_failure_probability": round(tot_p / n, 4),
                "status_counts": statuses,
                "open_alerts": self.alerts.count_open(),
            }

    # -- Internal ---------------------------------------------------------

    def _init_fleet(self, size: int) -> None:
        import random as _r
        rng = _r.Random(42)
        for i in range(size):
            vid = f"VIN-{1000 + i:04d}"
            self.vehicles[vid] = VehicleState(
                vehicle_id=vid,
                region=rng.choice(self.REGIONS),
                model_year=rng.choice([2023, 2024, 2025, 2026]),
                assigned_model=ab_router.assign(vid),
            )
            self.subsystem.reset(vid, seed=i + 1)
            self.drift.reset(vid)

    @staticmethod
    def _status(drift: float, prob: float) -> str:
        if prob >= CONFIG.failure_critical_prob or drift >= CONFIG.drift_critical_score:
            return "critical"
        if prob >= CONFIG.failure_warn_prob or drift >= CONFIG.drift_warn_score:
            return "warn"
        if prob >= 0.15 or drift >= 0.2:
            return "watch"
        return "healthy"

    def _run(self) -> None:
        while not self._stop.wait(CONFIG.tick_seconds):
            try:
                self._tick(CONFIG.tick_seconds * 30.0)  # advance 30 sim-seconds per tick
            except Exception:  # pragma: no cover - keep simulator alive
                logger.exception("Fleet tick failed; continuing")
                continue

    def _tick(self, dt: float) -> None:
        with self._lock:
            for v in self.vehicles.values():
                sample = self.subsystem.step(v.vehicle_id, dt)
                v.samples.append(sample)
                v.last_scenario = sample.scenario
                feats = self.subsystem.extract_features(list(v.samples))
                if not feats:
                    continue
                drift = self.drift.update(v.vehicle_id, feats)["score"]
                v.last_drift = drift
                model: FailureModel = model_registry.get(v.assigned_model)
                pred = model.predict(feats, drift)
                v.last_prediction = pred
                self.alerts.evaluate(v.vehicle_id, drift, pred, sample)
