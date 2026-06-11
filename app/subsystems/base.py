"""Abstract base class for any vehicle subsystem plugged into the platform."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class TelemetrySample:
    """A single timestamped telemetry sample for one vehicle."""

    t: float                # simulated seconds since epoch start
    actual: Dict[str, float]      # measured signals
    expected: Dict[str, float]    # digital-twin / HPC-simulation prediction
    fault_active: bool = False    # ground-truth flag from the simulator
    scenario: str = "nominal"     # e.g. "coolant_pump_degrading"


class Subsystem(ABC):
    """Plugin interface — implement these to add a new subsystem (HVAC, infotainment...)."""

    #: Stable, URL-safe identifier (e.g. "battery_thermal").
    id: str = ""
    #: Human-readable name shown in the UI.
    name: str = ""
    #: Short description for the executive summary.
    description: str = ""
    #: Signal channels emitted by :meth:`step`, in display order.
    signals: List[str] = []
    #: Units keyed by signal name (used by the dashboard).
    units: Dict[str, str] = {}

    @abstractmethod
    def reset(self, vehicle_id: str, seed: int) -> None:
        """Initialise per-vehicle simulator state."""

    @abstractmethod
    def step(self, vehicle_id: str, dt: float) -> TelemetrySample:
        """Advance the simulator by ``dt`` seconds and return the new sample."""

    @abstractmethod
    def extract_features(self, samples: List[TelemetrySample]) -> Dict[str, float]:
        """Compute the feature vector used by the drift / failure models."""
