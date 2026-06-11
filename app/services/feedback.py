"""Customer feedback intake — fuels the continuous-improvement / retraining loop."""

from __future__ import annotations

import time
import uuid
from collections import deque
from dataclasses import asdict, dataclass
from threading import RLock
from typing import Deque, Dict, List, Optional


@dataclass
class FeedbackEntry:
    id: str
    vehicle_id: Optional[str]
    subsystem_id: str
    label: str            # "true_positive" | "false_positive" | "missed_failure" | "comment"
    severity: str         # "info" | "warn" | "critical"
    comment: str
    submitted_by: str
    created_at: float
    incorporated_in_model: Optional[str] = None


class FeedbackStore:
    """In-memory feedback store; in production this is a durable queue feeding
    the retraining pipeline."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._items: Deque[FeedbackEntry] = deque(maxlen=1000)
        self._retraining_log: List[Dict[str, object]] = []

    def submit(
        self,
        vehicle_id: Optional[str],
        subsystem_id: str,
        label: str,
        comment: str,
        severity: str = "info",
        submitted_by: str = "customer",
    ) -> Dict[str, object]:
        entry = FeedbackEntry(
            id=str(uuid.uuid4())[:8],
            vehicle_id=vehicle_id,
            subsystem_id=subsystem_id,
            label=label,
            severity=severity,
            comment=comment,
            submitted_by=submitted_by,
            created_at=time.time(),
        )
        with self._lock:
            self._items.appendleft(entry)
        return asdict(entry)

    def list(self, limit: int = 100) -> List[Dict[str, object]]:
        with self._lock:
            return [asdict(e) for e in list(self._items)[:limit]]

    def trigger_retrain(self, new_version: str) -> Dict[str, object]:
        """Simulate ingestion of pending feedback into a new model version."""
        with self._lock:
            pending = [e for e in self._items if e.incorporated_in_model is None]
            for e in pending:
                e.incorporated_in_model = new_version
            event = {
                "id": str(uuid.uuid4())[:8],
                "timestamp": time.time(),
                "new_model_version": new_version,
                "samples_incorporated": len(pending),
                "feedback_ids": [e.id for e in pending],
            }
            self._retraining_log.append(event)
            return event

    def retraining_history(self) -> List[Dict[str, object]]:
        with self._lock:
            return list(self._retraining_log)


feedback_store = FeedbackStore()
