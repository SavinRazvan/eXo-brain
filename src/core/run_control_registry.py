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
import json
import sqlite3
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


class SQLiteRunControlRegistry:
    """SQLite-backed run control registry for multi-process consistency."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS run_control (
                    tenant_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    correlation_id TEXT NOT NULL,
                    transport TEXT NOT NULL,
                    status TEXT NOT NULL,
                    call_ids_json TEXT NOT NULL,
                    cancel_requested INTEGER NOT NULL,
                    cancel_reason TEXT NOT NULL,
                    started_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL,
                    finished_at_utc TEXT NOT NULL,
                    terminal_event TEXT NOT NULL,
                    terminal_message TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, run_id)
                )
                """
            )

    def start_run(
        self,
        *,
        tenant_id: str,
        session_id: str,
        run_id: str,
        correlation_id: str,
        transport: str,
    ) -> RunControlRecord:
        now = _utc_now()
        record = RunControlRecord(
            tenant_id=tenant_id,
            session_id=session_id,
            run_id=run_id,
            correlation_id=correlation_id or run_id,
            transport=transport,
            started_at_utc=now,
            updated_at_utc=now,
        )
        with self._lock, self._conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO run_control (
                    tenant_id, run_id, session_id, correlation_id, transport, status, call_ids_json,
                    cancel_requested, cancel_reason, started_at_utc, updated_at_utc, finished_at_utc,
                    terminal_event, terminal_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.tenant_id,
                    record.run_id,
                    record.session_id,
                    record.correlation_id,
                    record.transport,
                    record.status,
                    json.dumps([]),
                    0,
                    "",
                    record.started_at_utc,
                    record.updated_at_utc,
                    "",
                    "",
                    "",
                ),
            )
        return record

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, object]:
        return {
            "tenant_id": row["tenant_id"],
            "session_id": row["session_id"],
            "run_id": row["run_id"],
            "correlation_id": row["correlation_id"],
            "transport": row["transport"],
            "status": row["status"],
            "call_ids": sorted(json.loads(row["call_ids_json"])),
            "cancel_requested": bool(row["cancel_requested"]),
            "cancel_reason": row["cancel_reason"],
            "started_at_utc": row["started_at_utc"],
            "updated_at_utc": row["updated_at_utc"],
            "finished_at_utc": row["finished_at_utc"],
            "terminal_event": row["terminal_event"],
            "terminal_message": row["terminal_message"],
        }

    def record_tool_call(self, *, tenant_id: str, run_id: str, call_id: str) -> bool:
        normalized = str(call_id).strip()
        if not normalized:
            return False
        with self._lock, self._conn() as conn:
            row = conn.execute(
                "SELECT call_ids_json FROM run_control WHERE tenant_id = ? AND run_id = ?",
                (tenant_id, run_id),
            ).fetchone()
            if row is None:
                return False
            call_ids = set(json.loads(row["call_ids_json"]))
            call_ids.add(normalized)
            conn.execute(
                "UPDATE run_control SET call_ids_json = ?, updated_at_utc = ? WHERE tenant_id = ? AND run_id = ?",
                (json.dumps(sorted(call_ids)), _utc_now(), tenant_id, run_id),
            )
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
        now = _utc_now()
        with self._lock, self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM run_control WHERE tenant_id = ? AND run_id = ?",
                (tenant_id, run_id),
            ).fetchone()
            if row is None:
                return False
            conn.execute(
                """
                UPDATE run_control
                SET status = ?, terminal_event = ?, terminal_message = ?, updated_at_utc = ?, finished_at_utc = ?
                WHERE tenant_id = ? AND run_id = ?
                """,
                (status, terminal_event, terminal_message, now, now, tenant_id, run_id),
            )
            return True

    def request_cancel(self, *, tenant_id: str, run_id: str, reason: str) -> bool:
        with self._lock, self._conn() as conn:
            row = conn.execute(
                "SELECT status FROM run_control WHERE tenant_id = ? AND run_id = ?",
                (tenant_id, run_id),
            ).fetchone()
            if row is None:
                return False
            status = str(row["status"])
            new_status = status if status in {"completed", "errored", "cancelled"} else "cancel_requested"
            conn.execute(
                """
                UPDATE run_control
                SET cancel_requested = 1, cancel_reason = ?, status = ?, updated_at_utc = ?
                WHERE tenant_id = ? AND run_id = ?
                """,
                (reason, new_status, _utc_now(), tenant_id, run_id),
            )
            return True

    def get_run(self, *, tenant_id: str, run_id: str) -> dict[str, object] | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM run_control WHERE tenant_id = ? AND run_id = ?",
                (tenant_id, run_id),
            ).fetchone()
            return None if row is None else self._row_to_dict(row)

    def list_runs(self, *, tenant_id: str, limit: int = 50) -> list[dict[str, object]]:
        bounded = max(1, min(int(limit), 500))
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM run_control
                WHERE tenant_id = ?
                ORDER BY updated_at_utc DESC
                LIMIT ?
                """,
                (tenant_id, bounded),
            ).fetchall()
            return [self._row_to_dict(row) for row in rows]

    def call_ids_for_run(self, *, tenant_id: str, run_id: str) -> list[str]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT call_ids_json FROM run_control WHERE tenant_id = ? AND run_id = ?",
                (tenant_id, run_id),
            ).fetchone()
            if row is None:
                return []
            return sorted(json.loads(row["call_ids_json"]))

    def count_active_runs(self, *, tenant_id: str) -> int:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS c FROM run_control
                WHERE tenant_id = ? AND status IN ('running', 'cancel_requested')
                """,
                (tenant_id,),
            ).fetchone()
            return int(row["c"]) if row is not None else 0
