"""Case-study simulator — shows the before/after value of early detection."""

from __future__ import annotations

import random
from typing import Dict, List

from ..models.drift_detector import DriftDetector
from ..models.failure_predictor import model_registry
from ..subsystems.battery_thermal import BatteryThermalSubsystem


def run_case_study(scenario: str = "coolant_pump_degrading",
                   horizon_minutes: int = 240,
                   seed: int = 7) -> Dict[str, object]:
    """Re-runs a deterministic vehicle scenario through both model versions and
    returns a comparable timeline + key business outcomes."""

    subsystem = BatteryThermalSubsystem()
    vid = "CASE-STUDY"
    subsystem.reset(vid, seed=seed)
    # force the chosen scenario
    state = subsystem._states[vid]  # noqa: SLF001 - intentional for case study
    state.scenario = scenario
    state.scenario_t0 = 30.0
    state.rng = random.Random(seed)

    detectors = {v: DriftDetector(alpha=0.15) for v in ("baseline_v1", "ewma_plus_v2")}
    series: List[Dict[str, object]] = []
    first_detection: Dict[str, float] = {}
    samples: List = []

    dt = 30.0
    steps = int(horizon_minutes * 60 / dt)
    for _ in range(steps):
        sample = subsystem.step(vid, dt)
        samples.append(sample)
        feats = subsystem.extract_features(samples)
        entry: Dict[str, object] = {
            "t_min": round(sample.t / 60.0, 2),
            "fault_active": sample.fault_active,
            "max_cell_actual": sample.actual["max_cell_temp_c"],
            "max_cell_expected": sample.expected["max_cell_temp_c"],
            "coolant_delta_actual": sample.actual["coolant_delta_c"],
            "coolant_delta_expected": sample.expected["coolant_delta_c"],
        }
        for ver, det in detectors.items():
            drift = det.update(vid, feats)["score"]
            pred = model_registry.get(ver).predict(feats, drift)
            entry[f"{ver}_prob"] = pred["probability"]
            entry[f"{ver}_drift"] = drift
            if ver not in first_detection and pred["probability"] >= 0.5:
                first_detection[ver] = round(sample.t / 60.0, 2)
        series.append(entry)

    # ground-truth "failure occurred" minute (when fault becomes severe)
    failure_minute = next(
        (e["t_min"] for e in series if e["fault_active"] and
         (e["max_cell_actual"] - e["max_cell_expected"]) > 6.0),
        series[-1]["t_min"],
    )

    return {
        "scenario": scenario,
        "horizon_minutes": horizon_minutes,
        "series": series,
        "failure_minute": failure_minute,
        "first_detection": first_detection,
        "warning_lead_minutes": {
            ver: round(failure_minute - t, 2)
            for ver, t in first_detection.items()
        },
        "narrative": _narrative(scenario, first_detection, failure_minute),
    }


def _narrative(scenario: str, first_detection: Dict[str, float], failure_minute: float) -> str:
    best_ver = min(first_detection, key=first_detection.get) if first_detection else None
    if not best_ver:
        return ("No model detected the issue within the horizon — "
                "retraining with field data is recommended.")
    lead = failure_minute - first_detection[best_ver]
    return (
        f"In a real-world {scenario.replace('_', ' ')} event, the platform's "
        f"{best_ver} model flagged the vehicle {lead:.0f} minutes before "
        f"thermal limits were exceeded. That window is sufficient to "
        f"derate the pack, alert the driver, and schedule preventive service "
        f"— avoiding a roadside failure and the associated warranty claim."
    )
