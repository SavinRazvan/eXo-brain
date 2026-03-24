"""
File: sqlite_audit.py
Path: src/persistence/adapters/sqlite_audit.py
Role: Durable SQLite-backed audit store for tenant-scoped audit history.
Used By:
 - src/api/bootstrap.py
 - tests/modules/audit/
Depends On:
 - src/persistence/contracts.py
 - src/persistence/migrations.py
 - src/persistence/sqlite_connection.py
Notes:
 - Query preserves append order by an internal sequence id so replay/export remains deterministic.
 - File-backed writes run in a worker thread via asyncio.to_thread to avoid blocking the event loop.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import threading
from pathlib import Path
import sqlite3

from src.persistence.contracts import AuditRecord, AuditStore
from src.persistence.migrations import SQLiteMigration, apply_sqlite_migrations
from src.persistence.sqlite_connection import open_sqlite_file


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteAuditStore(AuditStore):
    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._db_path = str(db_path)
        self._memory_lock = threading.Lock()
        self._shared_conn: sqlite3.Connection | None = (
            sqlite3.connect(":memory:", check_same_thread=False)
            if self._db_path == ":memory:"
            else None
        )
        if self._shared_conn is not None:
            self._ensure_schema_sync(self._shared_conn)
        else:
            conn = open_sqlite_file(self._db_path)
            try:
                self._ensure_schema_sync(conn)
            finally:
                conn.close()

    def _connect_sync(self) -> sqlite3.Connection:
        if self._shared_conn is not None:
            return self._shared_conn
        return open_sqlite_file(self._db_path)

    def _connect(self) -> sqlite3.Connection:
        """Return the memory shared connection or a fresh file connection (tests/diagnostics)."""
        return self._connect_sync()

    def _ensure_schema_sync(self, conn: sqlite3.Connection) -> None:
        apply_sqlite_migrations(
            conn,
            [
                SQLiteMigration(
                    migration_id="audit_events.v1",
                    statements=(
                        """
                        CREATE TABLE IF NOT EXISTS audit_events (
                            sequence_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            event_id TEXT NOT NULL UNIQUE,
                            correlation_id TEXT NOT NULL,
                            tenant_id TEXT NOT NULL,
                            event_type TEXT NOT NULL,
                            payload_json TEXT NOT NULL,
                            created_at_utc TEXT NOT NULL
                        )
                        """,
                    ),
                )
            ],
        )

    def _row_to_record(self, row: tuple) -> AuditRecord:
        event_id, correlation_id, tenant_id, event_type, payload_json = row
        return AuditRecord(
            event_id=event_id,
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            event_type=event_type,
            payload=json.loads(payload_json),
        )

    def _append_sync(self, record: AuditRecord) -> None:
        def _do(conn: sqlite3.Connection) -> None:
            conn.execute(
                """
                INSERT INTO audit_events (
                    event_id, correlation_id, tenant_id, event_type, payload_json, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.event_id,
                    record.correlation_id,
                    record.tenant_id,
                    record.event_type,
                    json.dumps(record.payload),
                    _utc_now(),
                ),
            )
            conn.commit()

        if self._shared_conn is not None:
            with self._memory_lock:
                _do(self._shared_conn)
            return
        conn = self._connect_sync()
        try:
            _do(conn)
        finally:
            conn.close()

    def _query_sync(self, correlation_id: str, tenant_id: str) -> list[AuditRecord]:
        def _do(conn: sqlite3.Connection) -> list[AuditRecord]:
            rows = conn.execute(
                """
                SELECT event_id, correlation_id, tenant_id, event_type, payload_json
                FROM audit_events
                WHERE correlation_id = ? AND tenant_id = ?
                ORDER BY sequence_id ASC
                """,
                (correlation_id, tenant_id),
            ).fetchall()
            return [self._row_to_record(row) for row in rows]

        if self._shared_conn is not None:
            with self._memory_lock:
                return _do(self._shared_conn)
        conn = self._connect_sync()
        try:
            return _do(conn)
        finally:
            conn.close()

    def _list_sync(self, tenant_id: str, limit: int) -> list[AuditRecord]:
        bounded = max(1, min(int(limit), 1000))

        def _do(conn: sqlite3.Connection) -> list[AuditRecord]:
            rows = conn.execute(
                """
                SELECT event_id, correlation_id, tenant_id, event_type, payload_json
                FROM audit_events
                WHERE tenant_id = ?
                ORDER BY sequence_id DESC
                LIMIT ?
                """,
                (tenant_id, bounded),
            ).fetchall()
            return [self._row_to_record(row) for row in reversed(rows)]

        if self._shared_conn is not None:
            with self._memory_lock:
                return _do(self._shared_conn)
        conn = self._connect_sync()
        try:
            return _do(conn)
        finally:
            conn.close()

    def _cleanup_sync(self, tenant_id: str, max_records: int) -> int:
        bounded = max(int(max_records), 0)

        def _do(conn: sqlite3.Connection) -> int:
            total_row = conn.execute(
                "SELECT COUNT(1) FROM audit_events WHERE tenant_id = ?",
                (tenant_id,),
            ).fetchone()
            total = int(total_row[0]) if total_row else 0
            overflow = max(0, total - bounded)
            if overflow <= 0:
                return 0
            conn.execute(
                """
                DELETE FROM audit_events
                WHERE sequence_id IN (
                    SELECT sequence_id
                    FROM audit_events
                    WHERE tenant_id = ?
                    ORDER BY sequence_id ASC
                    LIMIT ?
                )
                """,
                (tenant_id, overflow),
            )
            conn.commit()
            return overflow

        if self._shared_conn is not None:
            with self._memory_lock:
                return _do(self._shared_conn)
        conn = self._connect_sync()
        try:
            return _do(conn)
        finally:
            conn.close()

    async def append_audit_event(self, record: AuditRecord) -> None:
        await asyncio.to_thread(self._append_sync, record)

    async def query_audit_events(self, correlation_id: str, tenant_id: str = "default") -> list[AuditRecord]:
        return await asyncio.to_thread(self._query_sync, correlation_id, tenant_id)

    async def list_audit_events(self, tenant_id: str = "default", limit: int = 100) -> list[AuditRecord]:
        return await asyncio.to_thread(self._list_sync, tenant_id, limit)

    async def cleanup_audit_events(self, tenant_id: str = "default", max_records: int = 1000) -> int:
        return await asyncio.to_thread(self._cleanup_sync, tenant_id, max_records)
