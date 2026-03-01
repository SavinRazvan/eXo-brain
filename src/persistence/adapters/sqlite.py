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
from src.persistence.contracts import (
    CheckpointRecord,
    CheckpointStatus,
    CheckpointStoreContract,
    PersistenceIsolationError,
    SessionRecord,
    SessionStore,
)


def _assert_tenant_match(stored_tenant_id: str, requested_tenant_id: str, entity_type: str) -> None:
    if stored_tenant_id != requested_tenant_id:
        raise PersistenceIsolationError(
            reason_code="PERSISTENCE_TENANT_ISOLATION_VIOLATION",
            message=f"{entity_type} belongs to a different tenant",
            tenant_id=stored_tenant_id,
            requested_tenant_id=requested_tenant_id,
        )


class SQLiteSessionStore(SessionStore):
    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._db_path = str(db_path)
        self._ensure_schema()

    async def save_session(self, record: SessionRecord) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO sessions (
                    tenant_id, session_id, run_id, job_id, task_id, agent_id, provider_id, correlation_id,
                    metadata_json, state, data_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, session_id) DO UPDATE SET
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
                    record.tenant_id,
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

    async def get_session(self, session_id: str, tenant_id: str = "default") -> SessionRecord | None:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT tenant_id, session_id, run_id, job_id, task_id, agent_id, provider_id, correlation_id, metadata_json, state, data_json
                FROM sessions
                WHERE tenant_id = ? AND session_id = ?
                """,
                (tenant_id, session_id),
            ).fetchone()
            if row is None:
                collision_row = conn.execute(
                    """
                    SELECT tenant_id FROM sessions WHERE session_id = ? LIMIT 1
                    """,
                    (session_id,),
                ).fetchone()
                if collision_row is not None:
                    _assert_tenant_match(
                        stored_tenant_id=collision_row[0],
                        requested_tenant_id=tenant_id,
                        entity_type="session",
                    )
                return None
        _assert_tenant_match(stored_tenant_id=row[0], requested_tenant_id=tenant_id, entity_type="session")
        session = SessionContext(
            session_id=row[1],
            run_id=row[2],
            job_id=row[3],
            task_id=row[4],
            agent_id=row[5],
            provider_id=row[6],
            correlation_id=row[7],
            metadata=json.loads(row[8]),
        )
        return SessionRecord(session=session, tenant_id=row[0], state=row[9], data=json.loads(row[10]))

    def _ensure_schema(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    tenant_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    provider_id TEXT NOT NULL,
                    correlation_id TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    state TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, session_id)
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
                INSERT INTO checkpoints (tenant_id, job_id, node_id, status, attempt, reason_code, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, job_id, node_id) DO UPDATE SET
                    status=excluded.status,
                    attempt=excluded.attempt,
                    reason_code=excluded.reason_code,
                    payload_json=excluded.payload_json
                """,
                (
                    checkpoint.tenant_id,
                    checkpoint.job_id,
                    checkpoint.node_id,
                    checkpoint.status.value,
                    checkpoint.attempt,
                    checkpoint.reason_code,
                    json.dumps(checkpoint.payload),
                ),
            )
            conn.commit()

    async def list_checkpoints(self, job_id: str, tenant_id: str = "default") -> list[CheckpointRecord]:
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(
                """
                SELECT tenant_id, job_id, node_id, status, attempt, reason_code, payload_json
                FROM checkpoints
                WHERE tenant_id = ? AND job_id = ?
                ORDER BY node_id ASC
                """,
                (tenant_id, job_id),
            ).fetchall()
        checkpoints = [self._row_to_checkpoint(row) for row in rows]
        for checkpoint in checkpoints:
            _assert_tenant_match(
                stored_tenant_id=checkpoint.tenant_id,
                requested_tenant_id=tenant_id,
                entity_type="checkpoint",
            )
        return checkpoints

    async def get_checkpoint(self, job_id: str, node_id: str, tenant_id: str = "default") -> CheckpointRecord | None:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT tenant_id, job_id, node_id, status, attempt, reason_code, payload_json
                FROM checkpoints
                WHERE tenant_id = ? AND job_id = ? AND node_id = ?
                """,
                (tenant_id, job_id, node_id),
            ).fetchone()
            if row is None:
                collision_row = conn.execute(
                    """
                    SELECT tenant_id FROM checkpoints WHERE job_id = ? AND node_id = ? LIMIT 1
                    """,
                    (job_id, node_id),
                ).fetchone()
                if collision_row is not None:
                    _assert_tenant_match(
                        stored_tenant_id=collision_row[0],
                        requested_tenant_id=tenant_id,
                        entity_type="checkpoint",
                    )
                return None
        checkpoint = self._row_to_checkpoint(row)
        _assert_tenant_match(
            stored_tenant_id=checkpoint.tenant_id,
            requested_tenant_id=tenant_id,
            entity_type="checkpoint",
        )
        return checkpoint

    def _ensure_schema(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS checkpoints (
                    tenant_id TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    reason_code TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, job_id, node_id)
                )
                """
            )
            conn.commit()

    def _row_to_checkpoint(self, row: tuple[str, str, str, str, int, str, str]) -> CheckpointRecord:
        return CheckpointRecord(
            tenant_id=row[0],
            job_id=row[1],
            node_id=row[2],
            status=CheckpointStatus(row[3]),
            attempt=row[4],
            reason_code=row[5],
            payload=json.loads(row[6]),
        )

