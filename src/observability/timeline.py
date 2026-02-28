"""
File: timeline.py
Path: src/observability/timeline.py
Role: Runtime timeline reconstruction from structured events.
Used By:
 - src/core/scheduler.py
 - src/core/background_runtime.py
Depends On:
 - dataclasses
Notes:
 - Timeline entries are ordered append-only records keyed by correlation/job IDs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class TimelineEntry:
    correlation_id: str
    event: str
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class RuntimeTimeline:
    def __init__(self) -> None:
        self._entries: list[TimelineEntry] = []

    def append(self, correlation_id: str, event: str, payload: dict[str, Any] | None = None) -> None:
        self._entries.append(
            TimelineEntry(
                correlation_id=correlation_id,
                event=event,
                payload=dict(payload or {}),
            )
        )

    def entries_for(self, correlation_id: str) -> list[TimelineEntry]:
        return [entry for entry in self._entries if entry.correlation_id == correlation_id]

    def all_entries(self) -> list[TimelineEntry]:
        return list(self._entries)
