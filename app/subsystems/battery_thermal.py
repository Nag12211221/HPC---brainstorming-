"""Battery Thermal Management subsystem.

We model a Li-ion pack with liquid cooling. The digital twin is the
"HPC simulation prediction" of expected pack temperature given the
current load profile. Drift is what we observe in the field versus that
prediction.

Failure scenarios that the simulator can inject:

* ``coolant_pump_degrading`` — coolant flow slowly drops, ΔT widens.
* ``cell_imbalance`` — one cell heats up faster than the rest.
* ``sensor_bias`` — sensor reports lower-than-actual, masking issues.
* ``nominal`` — healthy behaviour.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List

from .base import Subsystem, TelemetrySample


@dataclass
class _BatteryState:
    rng: random.Random
    t: float = 0.0
    # Drive cycle phase
    load_phase: float = 0.0
    # Health degradation factors (1.0 == healthy, 0.0 == fully failed)
    pump_health: float = 1.0
    cell_balance: float = 1.0
    sensor_bias_c: float = 0.0
    # Active scenario and when it started
    scenario: str = "nominal"
    scenario_t0: float = 0.0
    # Smoothed coolant inlet temp
    coolant_in_c: float = 25.0
    ambient_c: float = 24.0


class BatteryThermalSubsystem(Subsystem):
    id = "battery_thermal"
    name = "Battery Thermal Management"
    description = (
        "High-voltage battery pack thermal control. Monitors cell temperatures, "
        "coolant ΔT, current draw and pack voltage to predict thermal runaway, "
        "coolant pump degradation, and cell imbalance failures."
    )
    signals = [
        "pack_temp_c",
        "max_cell_temp_c",
        "coolant_delta_c",
        "coolant_flow_lpm",
        "current_a",
        "pack_voltage_v",
        "soc_pct",
    ]
    units = {
        "pack_temp_c": "°C",
        "max_cell_temp_c": "°C",
        "coolant_delta_c": "°C",
        "coolant_flow_lpm": "L/min",
        "current_a": "A",
        "pack_voltage_v": "V",
        "soc_pct": "%",
    }

    # Scenarios with weighted probability of being assigned at vehicle init
    _SCENARIO_WEIGHTS = [
        ("nominal", 0.55),
        ("coolant_pump_degrading", 0.18),
        ("cell_imbalance", 0.15),
        ("sensor_bias", 0.12),
    ]

    def __init__(self) -> None:
        self._states: Dict[str, _BatteryState] = {}

    # -- Subsystem API ----------------------------------------------------

    def reset(self, vehicle_id: str, seed: int) -> None:
        rng = random.Random(seed)
        scenario = self._pick_scenario(rng)
        self._states[vehicle_id] = _BatteryState(
            rng=rng,
            scenario=scenario,
            scenario_t0=rng.uniform(20.0, 120.0),  # latency before fault appears
            ambient_c=rng.uniform(18.0, 32.0),
            coolant_in_c=rng.uniform(22.0, 28.0),
        )

    def step(self, vehicle_id: str, dt: float) -> TelemetrySample:
        st = self._states.get(vehicle_id)
        if st is None:
            self.reset(vehicle_id, seed=hash(vehicle_id) & 0xFFFFFFFF)
            st = self._states[vehicle_id]

        st.t += dt
        st.load_phase += dt * 0.05
        self._progress_fault(st)

        # Drive-cycle current (sinusoidal + noise), 0–250 A
        current = 120.0 + 110.0 * math.sin(st.load_phase) + st.rng.gauss(0, 6)
        current = max(0.0, current)

        # SoC slowly drains
        soc = max(5.0, 95.0 - (st.t % 3600) / 60.0)

        # Pack voltage drops with current (internal resistance) and SoC
        pack_voltage = 400.0 - 0.05 * current - (95.0 - soc) * 0.4 + st.rng.gauss(0, 0.3)

        # Heat generation proportional to I^2 * R_eff
        heat_w = current * current * 0.0006

        # Cooling capacity (degrades with pump health)
        flow = (12.0 * st.pump_health) + st.rng.gauss(0, 0.15)
        flow = max(0.5, flow)
        cooling_w = flow * 380.0

        # ΔT across coolant loop
        delta_t = max(1.5, (heat_w - cooling_w * 0.04) / max(flow * 90.0, 1.0) + 3.0)

        # Pack temperature (low-pass on heat - cooling)
        target_pack_t = st.ambient_c + 8.0 + heat_w / 12.0 - (flow - 6.0) * 0.4
        pack_temp = target_pack_t + st.rng.gauss(0, 0.4)

        # Max cell temperature affected by imbalance
        imbalance_bump = (1.0 - st.cell_balance) * 18.0
        max_cell_t = pack_temp + 2.5 + imbalance_bump + st.rng.gauss(0, 0.3)

        # ---- Sensor view (what the field sees) — sensor bias hides the truth
        reported_pack = pack_temp - st.sensor_bias_c
        reported_cell = max_cell_t - st.sensor_bias_c

        actual = {
            "pack_temp_c": round(reported_pack, 2),
            "max_cell_temp_c": round(reported_cell, 2),
            "coolant_delta_c": round(delta_t, 2),
            "coolant_flow_lpm": round(flow, 2),
            "current_a": round(current, 1),
            "pack_voltage_v": round(pack_voltage, 2),
            "soc_pct": round(soc, 1),
        }

        # ---- Digital twin (HPC sim) — assumes healthy hardware, no bias
        twin_flow = 12.0
        twin_cooling = twin_flow * 380.0
        twin_delta = max(1.5, (heat_w - twin_cooling * 0.04) / (twin_flow * 90.0) + 3.0)
        twin_pack = st.ambient_c + 8.0 + heat_w / 12.0 - (twin_flow - 6.0) * 0.4
        twin_cell = twin_pack + 2.5

        expected = {
            "pack_temp_c": round(twin_pack, 2),
            "max_cell_temp_c": round(twin_cell, 2),
            "coolant_delta_c": round(twin_delta, 2),
            "coolant_flow_lpm": round(twin_flow, 2),
            "current_a": round(current, 1),
            "pack_voltage_v": round(400.0 - 0.05 * current - (95.0 - soc) * 0.4, 2),
            "soc_pct": round(soc, 1),
        }

        fault_active = st.scenario != "nominal" and st.t >= st.scenario_t0
        return TelemetrySample(
            t=st.t,
            actual=actual,
            expected=expected,
            fault_active=fault_active,
            scenario=st.scenario if fault_active else "nominal",
        )

    def extract_features(self, samples: List[TelemetrySample]) -> Dict[str, float]:
        """Per-channel residual (actual - expected) and rolling slope features."""
        if not samples:
            return {}
        last_n = samples[-30:]
        feats: Dict[str, float] = {}
        for ch in ("pack_temp_c", "max_cell_temp_c", "coolant_delta_c", "coolant_flow_lpm"):
            residuals = [s.actual[ch] - s.expected[ch] for s in last_n]
            mean_r = sum(residuals) / len(residuals)
            # simple slope across the window
            slope = (residuals[-1] - residuals[0]) / max(len(residuals) - 1, 1)
            feats[f"residual_mean_{ch}"] = mean_r
            feats[f"residual_slope_{ch}"] = slope
        feats["max_cell_temp_c"] = last_n[-1].actual["max_cell_temp_c"]
        feats["coolant_delta_c"] = last_n[-1].actual["coolant_delta_c"]
        feats["coolant_flow_lpm"] = last_n[-1].actual["coolant_flow_lpm"]
        return feats

    # -- Internal helpers -------------------------------------------------

    def _pick_scenario(self, rng: random.Random) -> str:
        r = rng.random()
        acc = 0.0
        for name, w in self._SCENARIO_WEIGHTS:
            acc += w
            if r <= acc:
                return name
        return "nominal"

    @staticmethod
    def _progress_fault(st: _BatteryState) -> None:
        if st.scenario == "nominal" or st.t < st.scenario_t0:
            return
        # progress measured in simulated minutes since onset
        elapsed_min = (st.t - st.scenario_t0) / 60.0
        if st.scenario == "coolant_pump_degrading":
            st.pump_health = max(0.35, 1.0 - elapsed_min * 0.012)
        elif st.scenario == "cell_imbalance":
            st.cell_balance = max(0.30, 1.0 - elapsed_min * 0.010)
        elif st.scenario == "sensor_bias":
            st.sensor_bias_c = min(6.0, elapsed_min * 0.08)
            # latent degradation also creeps in
            st.pump_health = max(0.55, 1.0 - elapsed_min * 0.004)
