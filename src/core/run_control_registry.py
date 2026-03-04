"""
File: run_control_registry.py
Path: src/core/run_control_registry.py
Role: Canonical in-memory registry for run lifecycle state and cancellation metadata.
Used By:
 - src/api/bootstrap.py
 - src/api/routers/turns.py
 - src/api/routers/runtime_control.py
Depends On:
 - dataclasses
 - threading
Notes:
 - This registry is process-local and intended for operational control surfaces.
 - Keys are tenant-scoped to preserve isolation guarantees.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import threading


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class RunControlRecord:
    tenant_id: str
    session_id: str
    run_id: str
    correlation_id: str
    transport: str
    status: str = "running"
    call_ids: set[str] = field(default_factory=set)
    cancel_requested: bool = False
    cancel_reason: str = ""
    started_at_utc: str = field(default_factory=_utc_now)
    updated_at_utc: str = field(default_factory=_utc_now)
    finished_at_utc: str = ""
    terminal_event: str = ""
    terminal_message: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "tenant_id": self.tenant_id,
            "session_id": self.session_id,
            "run_id": self.run_id,
            "correlation_id": self.correlation_id,
            "transport": self.transport,
            "status": self.status,
            "call_ids": sorted(self.call_ids),
            "cancel_requested": self.cancel_requested,
            "cancel_reason": self.cancel_reason,
            "started_at_utc": self.started_at_utc,
            "updated_at_utc": self.updated_at_utc,
            "finished_at_utc": self.finished_at_utc,
            "terminal_event": self.terminal_event,
            "terminal_message": self.terminal_message,
        }


class RunControlRegistry:
    """Track run lifecycle and cancellation control metadata by tenant/run."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: dict[tuple[str, str], RunControlRecord] = {}

    def start_run(
        self,
        *,
        tenant_id: str,
        session_id: str,
        run_id: str,
        correlation_id: str,
        transport: str,
    ) -> RunControlRecord:
        key = (tenant_id, run_id)
        with self._lock:
            record = RunControlRecord(
                tenant_id=tenant_id,
                session_id=session_id,
                run_id=run_id,
                correlation_id=correlation_id or run_id,
                transport=transport,
            )
            self._records[key] = record
            return record

    def record_tool_call(self, *, tenant_id: str, run_id: str, call_id: str) -> bool:
        normalized = str(call_id).strip()
        if not normalized:
            return False
        key = (tenant_id, run_id)
        with self._lock:
            record = self._records.get(key)
            if record is None:
                return False
            record.call_ids.add(normalized)
            record.updated_at_utc = _utc_now()
            return True

    def mark_terminal(
        self,
        *,
        tenant_id: str,
        run_id: str,
        status: str,
        terminal_event: str,
        terminal_message: str = "",
    ) -> bool:
        key = (tenant_id, run_id)
        with self._lock:
            record = self._records.get(key)
            if record is None:
                return False
            record.status = status
            record.terminal_event = terminal_event
            record.terminal_message = terminal_message
            now = _utc_now()
            record.updated_at_utc = now
            record.finished_at_utc = now
            return True

    def request_cancel(self, *, tenant_id: str, run_id: str, reason: str) -> bool:
        key = (tenant_id, run_id)
        with self._lock:
            record = self._records.get(key)
            if record is None:
                return False
            record.cancel_requested = True
            record.cancel_reason = reason
            if record.status not in {"completed", "errored", "cancelled"}:
                record.status = "cancel_requested"
            record.updated_at_utc = _utc_now()
            return True

    def get_run(self, *, tenant_id: str, run_id: str) -> dict[str, object] | None:
        key = (tenant_id, run_id)
        with self._lock:
            record = self._records.get(key)
            return None if record is None else record.to_dict()

    def list_runs(self, *, tenant_id: str, limit: int = 50) -> list[dict[str, object]]:
        bounded = max(1, min(int(limit), 500))
        with self._lock:
            records = [r for r in self._records.values() if r.tenant_id == tenant_id]
            records.sort(key=lambda r: r.updated_at_utc, reverse=True)
            return [r.to_dict() for r in records[:bounded]]

    def call_ids_for_run(self, *, tenant_id: str, run_id: str) -> list[str]:
        key = (tenant_id, run_id)
        with self._lock:
            record = self._records.get(key)
            if record is None:
                return []
            return sorted(record.call_ids)

    def count_active_runs(self, *, tenant_id: str) -> int:
        active_statuses = {"running", "cancel_requested"}
        with self._lock:
            return sum(
                1
                for record in self._records.values()
                if record.tenant_id == tenant_id and record.status in active_statuses
            )
