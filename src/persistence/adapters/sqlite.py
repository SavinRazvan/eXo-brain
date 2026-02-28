"""
File: sqlite.py
Path: src/persistence/adapters/sqlite.py
Role: SQLite-backed persistence adapters for session and checkpoint contracts.
Used By:
 - tests/integration/test_persistence_adapter_parity.py
Depends On:
 - src/persistence/contracts.py
 - src/core/session_context.py
Notes:
 - Uses sqlite upsert semantics to keep contract behavior deterministic.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from src.core.session_context import SessionContext
from src.persistence.contracts import CheckpointRecord, CheckpointStatus, CheckpointStoreContract, SessionRecord, SessionStore


class SQLiteSessionStore(SessionStore):
    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._db_path = str(db_path)
        self._ensure_schema()

    async def save_session(self, record: SessionRecord) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO sessions (
                    session_id, run_id, job_id, task_id, agent_id, provider_id, correlation_id,
                    metadata_json, state, data_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    run_id=excluded.run_id,
                    job_id=excluded.job_id,
                    task_id=excluded.task_id,
                    agent_id=excluded.agent_id,
                    provider_id=excluded.provider_id,
                    correlation_id=excluded.correlation_id,
                    metadata_json=excluded.metadata_json,
                    state=excluded.state,
                    data_json=excluded.data_json
                """,
                (
                    record.session.session_id,
                    record.session.run_id,
                    record.session.job_id,
                    record.session.task_id,
                    record.session.agent_id,
                    record.session.provider_id,
                    record.session.correlation_id,
                    json.dumps(record.session.metadata),
                    record.state,
                    json.dumps(record.data),
                ),
            )
            conn.commit()

    async def get_session(self, session_id: str) -> SessionRecord | None:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT session_id, run_id, job_id, task_id, agent_id, provider_id, correlation_id, metadata_json, state, data_json
                FROM sessions
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        session = SessionContext(
            session_id=row[0],
            run_id=row[1],
            job_id=row[2],
            task_id=row[3],
            agent_id=row[4],
            provider_id=row[5],
            correlation_id=row[6],
            metadata=json.loads(row[7]),
        )
        return SessionRecord(session=session, state=row[8], data=json.loads(row[9]))

    def _ensure_schema(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    provider_id TEXT NOT NULL,
                    correlation_id TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    state TEXT NOT NULL,
                    data_json TEXT NOT NULL
                )
                """
            )
            conn.commit()


class SQLiteCheckpointStore(CheckpointStoreContract):
    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._db_path = str(db_path)
        self._ensure_schema()

    async def save_checkpoint(self, checkpoint: CheckpointRecord) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO checkpoints (job_id, node_id, status, attempt, reason_code, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id, node_id) DO UPDATE SET
                    status=excluded.status,
                    attempt=excluded.attempt,
                    reason_code=excluded.reason_code,
                    payload_json=excluded.payload_json
                """,
                (
                    checkpoint.job_id,
                    checkpoint.node_id,
                    checkpoint.status.value,
                    checkpoint.attempt,
                    checkpoint.reason_code,
                    json.dumps(checkpoint.payload),
                ),
            )
            conn.commit()

    async def list_checkpoints(self, job_id: str) -> list[CheckpointRecord]:
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(
                """
                SELECT job_id, node_id, status, attempt, reason_code, payload_json
                FROM checkpoints
                WHERE job_id = ?
                ORDER BY node_id ASC
                """,
                (job_id,),
            ).fetchall()
        return [self._row_to_checkpoint(row) for row in rows]

    async def get_checkpoint(self, job_id: str, node_id: str) -> CheckpointRecord | None:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT job_id, node_id, status, attempt, reason_code, payload_json
                FROM checkpoints
                WHERE job_id = ? AND node_id = ?
                """,
                (job_id, node_id),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_checkpoint(row)

    def _ensure_schema(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS checkpoints (
                    job_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    reason_code TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (job_id, node_id)
                )
                """
            )
            conn.commit()

    def _row_to_checkpoint(self, row: tuple[str, str, str, int, str, str]) -> CheckpointRecord:
        return CheckpointRecord(
            job_id=row[0],
            node_id=row[1],
            status=CheckpointStatus(row[2]),
            attempt=row[3],
            reason_code=row[4],
            payload=json.loads(row[5]),
        )
