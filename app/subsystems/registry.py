"""Subsystem registry — enables incremental addition of new subsystems."""

from __future__ import annotations

from typing import Dict, List

from .base import Subsystem


class SubsystemRegistry:
    """In-memory registry; in production this would be backed by a service catalog."""

    def __init__(self) -> None:
        self._items: Dict[str, Subsystem] = {}

    def register(self, subsystem: Subsystem) -> None:
        if not subsystem.id:
            raise ValueError("Subsystem must define a non-empty id")
        self._items[subsystem.id] = subsystem

    def get(self, sid: str) -> Subsystem:
        if sid not in self._items:
            raise KeyError(f"Unknown subsystem '{sid}'")
        return self._items[sid]

    def all(self) -> List[Subsystem]:
        return list(self._items.values())

    def ids(self) -> List[str]:
        return list(self._items.keys())


registry = SubsystemRegistry()
