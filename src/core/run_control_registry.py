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
 - SQLite backend stores per-tool-call ids in append-only rows (not JSON blob rewrites).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import sqlite3
import threading

from src.persistence.migrations import SQLiteMigration, apply_sqlite_migrations
from src.persistence.sqlite_connection import open_sqlite_file


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


_TERMINAL_STATUSES = frozenset({"completed", "errored", "cancelled"})


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

    def __init__(self, *, max_terminal_records_per_tenant: int = 0) -> None:
        self._lock = threading.Lock()
        self._records: dict[tuple[str, str], RunControlRecord] = {}
        self._max_terminal_records_per_tenant = max(0, int(max_terminal_records_per_tenant))

    def _prune_memory_terminals_unlocked(self, tenant_id: str) -> None:
        cap = self._max_terminal_records_per_tenant
        if cap <= 0:
            return
        matching = [
            r
            for r in self._records.values()
            if r.tenant_id == tenant_id and r.status in _TERMINAL_STATUSES
        ]
        overflow = len(matching) - cap
        if overflow <= 0:
            return
        matching.sort(key=lambda r: (r.finished_at_utc or r.started_at_utc, r.run_id))
        for r in matching[:overflow]:
            self._records.pop((r.tenant_id, r.run_id), None)

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
            self._prune_memory_terminals_unlocked(tenant_id)
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

    def __init__(self, db_path: str, *, max_terminal_records_per_tenant: int = 0) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._max_terminal_records_per_tenant = max(0, int(max_terminal_records_per_tenant))
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        return open_sqlite_file(self._db_path)

    def _init_db(self) -> None:
        with self._conn() as conn:
            apply_sqlite_migrations(
                conn,
                [
                    SQLiteMigration(
                        migration_id="run_control.v1",
                        statements=(
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
                            """,
                        ),
                    ),
                    SQLiteMigration(
                        migration_id="run_control.v2_tool_calls",
                        statements=(
                            """
                            CREATE TABLE IF NOT EXISTS run_control_tool_calls (
                                tenant_id TEXT NOT NULL,
                                run_id TEXT NOT NULL,
                                call_id TEXT NOT NULL,
                                created_at_utc TEXT NOT NULL,
                                PRIMARY KEY (tenant_id, run_id, call_id)
                            )
                            """,
                            """
                            CREATE INDEX IF NOT EXISTS idx_run_control_tool_calls_tenant_run
                            ON run_control_tool_calls (tenant_id, run_id)
                            """,
                            """
                            INSERT OR IGNORE INTO run_control_tool_calls (
                                tenant_id, run_id, call_id, created_at_utc
                            )
                            SELECT rc.tenant_id, rc.run_id, je.value, rc.started_at_utc
                            FROM run_control AS rc, json_each(rc.call_ids_json) AS je
                            """,
                        ),
                    ),
                ],
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

    def _row_to_dict(self, row: sqlite3.Row, call_ids: list[str]) -> dict[str, object]:
        return {
            "tenant_id": row["tenant_id"],
            "session_id": row["session_id"],
            "run_id": row["run_id"],
            "correlation_id": row["correlation_id"],
            "transport": row["transport"],
            "status": row["status"],
            "call_ids": sorted(call_ids),
            "cancel_requested": bool(row["cancel_requested"]),
            "cancel_reason": row["cancel_reason"],
            "started_at_utc": row["started_at_utc"],
            "updated_at_utc": row["updated_at_utc"],
            "finished_at_utc": row["finished_at_utc"],
            "terminal_event": row["terminal_event"],
            "terminal_message": row["terminal_message"],
        }

    def _call_ids_for_runs(self, conn: sqlite3.Connection, tenant_id: str, run_ids: list[str]) -> dict[str, list[str]]:
        if not run_ids:
            return {}
        placeholders = ",".join("?" * len(run_ids))
        cur = conn.execute(
            f"""
            SELECT run_id, call_id FROM run_control_tool_calls
            WHERE tenant_id = ? AND run_id IN ({placeholders})
            ORDER BY rowid
            """,
            (tenant_id, *run_ids),
        )
        by_run: dict[str, list[str]] = {}
        for r in cur.fetchall():
            rid = str(r["run_id"])
            by_run.setdefault(rid, []).append(str(r["call_id"]))
        return by_run

    def record_tool_call(self, *, tenant_id: str, run_id: str, call_id: str) -> bool:
        normalized = str(call_id).strip()
        if not normalized:
            return False
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
                INSERT OR IGNORE INTO run_control_tool_calls (
                    tenant_id, run_id, call_id, created_at_utc
                ) VALUES (?, ?, ?, ?)
                """,
                (tenant_id, run_id, normalized, now),
            )
            conn.execute(
                "UPDATE run_control SET updated_at_utc = ? WHERE tenant_id = ? AND run_id = ?",
                (now, tenant_id, run_id),
            )
            return True

    def _prune_sqlite_terminals(self, conn: sqlite3.Connection, tenant_id: str) -> None:
        cap = self._max_terminal_records_per_tenant
        if cap <= 0:
            return
        statuses = tuple(sorted(_TERMINAL_STATUSES))
        row = conn.execute(
            f"""
            SELECT COUNT(*) AS c FROM run_control
            WHERE tenant_id = ? AND status IN ({",".join("?" * len(statuses))})
            """,
            (tenant_id, *statuses),
        ).fetchone()
        total = int(row["c"]) if row is not None else 0
        overflow = total - cap
        if overflow <= 0:
            return
        old_rows = conn.execute(
            f"""
            SELECT run_id FROM run_control
            WHERE tenant_id = ? AND status IN ({",".join("?" * len(statuses))})
            ORDER BY datetime(finished_at_utc) ASC, started_at_utc ASC, run_id ASC
            LIMIT ?
            """,
            (tenant_id, *statuses, overflow),
        ).fetchall()
        for r in old_rows:
            rid = str(r["run_id"])
            conn.execute(
                "DELETE FROM run_control_tool_calls WHERE tenant_id = ? AND run_id = ?",
                (tenant_id, rid),
            )
            conn.execute(
                "DELETE FROM run_control WHERE tenant_id = ? AND run_id = ?",
                (tenant_id, rid),
            )

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
            self._prune_sqlite_terminals(conn, tenant_id)
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
            if row is None:
                return None
            ids = self._call_ids_for_runs(conn, tenant_id, [run_id]).get(run_id, [])
            if not ids:
                legacy = json.loads(row["call_ids_json"])
                if isinstance(legacy, list):
                    ids = [str(x) for x in legacy]
            return self._row_to_dict(row, ids)

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
            run_ids = [str(r["run_id"]) for r in rows]
            by_run = self._call_ids_for_runs(conn, tenant_id, run_ids)
            out: list[dict[str, object]] = []
            for row in rows:
                rid = str(row["run_id"])
                ids = by_run.get(rid, [])
                if not ids:
                    legacy = json.loads(row["call_ids_json"])
                    if isinstance(legacy, list):
                        ids = [str(x) for x in legacy]
                out.append(self._row_to_dict(row, ids))
            return out

    def call_ids_for_run(self, *, tenant_id: str, run_id: str) -> list[str]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT call_id FROM run_control_tool_calls
                WHERE tenant_id = ? AND run_id = ?
                ORDER BY rowid
                """,
                (tenant_id, run_id),
            ).fetchall()
            if rows:
                return [str(r["call_id"]) for r in rows]
            row = conn.execute(
                "SELECT call_ids_json FROM run_control WHERE tenant_id = ? AND run_id = ?",
                (tenant_id, run_id),
            ).fetchone()
            if row is None:
                return []
            legacy = json.loads(row["call_ids_json"])
            return sorted(str(x) for x in legacy) if isinstance(legacy, list) else []

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
