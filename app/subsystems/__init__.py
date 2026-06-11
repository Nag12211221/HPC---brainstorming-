"""Subsystem package — pluggable telemetry+model definitions."""

from .registry import SubsystemRegistry, registry  # noqa: F401
from .battery_thermal import BatteryThermalSubsystem  # noqa: F401

# Default registration so the API exposes the shipped subsystem out of the box.
registry.register(BatteryThermalSubsystem())
