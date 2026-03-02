"""
File: sqlite.py
Path: src/persistence/adapters/sqlite.py
Role: SQLite-backed persistence adapters for session, checkpoint, tool, agent, and API key contracts.
Used By:
 - src/api/bootstrap.py
 - src/api/startup.py
 - tests/modules/core/test_persistence_adapter_parity.py
 - tests/modules/persistence/test_tool_agent_stores.py
 - tests/modules/api/test_auth_apikey.py
Depends On:
 - src/persistence/contracts.py
 - src/core/session_context.py
Notes:
 - Uses sqlite upsert semantics to keep contract behavior deterministic.
 - All stores share the same db_path; each uses a separate table.
 - In-memory (':memory:') stores keep a single shared connection to prevent per-call resets.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from src.core.session_context import SessionContext
from src.persistence.contracts import (
    AgentStore,
    ApiKeyRecord,
    ApiKeyStore,
    CheckpointRecord,
    CheckpointStatus,
    CheckpointStoreContract,
    PersistedAgentRecord,
    PersistedToolRecord,
    PersistenceIsolationError,
    SessionRecord,
    SessionStore,
    ToolStore,
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


class SQLiteToolStore(ToolStore):
    """SQLite-backed tool store using upsert semantics.

    For ':memory:' databases a single shared connection is kept alive for the
    lifetime of the store instance; file-based databases use a new connection per
    operation so multiple processes can share the same file safely.
    """

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._db_path = str(db_path)
        # Keep a persistent connection for in-memory dbs (each connect() creates a fresh db).
        self._shared_conn: sqlite3.Connection | None = (
            sqlite3.connect(":memory:", check_same_thread=False)
            if self._db_path == ":memory:"
            else None
        )
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        if self._shared_conn is not None:
            return self._shared_conn
        return sqlite3.connect(self._db_path)

    async def save_tool(self, tenant_id: str, record: PersistedToolRecord) -> None:
        data = {
            "risk_tier": record.risk_tier,
            "is_state_changing": record.is_state_changing,
            "timeout_ms": record.timeout_ms,
            "description": record.description,
            "parameters_schema": record.parameters_schema,
            "metadata": record.metadata,
        }
        conn = self._connect()
        conn.execute(
            """
            INSERT INTO tools (tenant_id, tool_name, handler_ref, data_json)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(tenant_id, tool_name) DO UPDATE SET
                handler_ref=excluded.handler_ref,
                data_json=excluded.data_json
            """,
            (tenant_id, record.name, record.handler_ref, json.dumps(data)),
        )
        conn.commit()

    async def delete_tool(self, tenant_id: str, tool_name: str) -> None:
        conn = self._connect()
        conn.execute(
            "DELETE FROM tools WHERE tenant_id = ? AND tool_name = ?",
            (tenant_id, tool_name),
        )
        conn.commit()

    async def list_tools(self, tenant_id: str) -> list[PersistedToolRecord]:
        conn = self._connect()
        rows = conn.execute(
            """
            SELECT tool_name, handler_ref, data_json
            FROM tools
            WHERE tenant_id = ?
            ORDER BY tool_name ASC
            """,
            (tenant_id,),
        ).fetchall()
        records = []
        for row in rows:
            tool_name, handler_ref, data_json = row
            data = json.loads(data_json)
            records.append(
                PersistedToolRecord(
                    name=tool_name,
                    handler_ref=handler_ref,
                    tenant_id=tenant_id,
                    risk_tier=data.get("risk_tier", "low"),
                    is_state_changing=data.get("is_state_changing", False),
                    timeout_ms=data.get("timeout_ms", 30000),
                    description=data.get("description", ""),
                    parameters_schema=data.get("parameters_schema", {}),
                    metadata=data.get("metadata", {}),
                )
            )
        return records

    async def list_tenant_ids(self) -> list[str]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT DISTINCT tenant_id FROM tools ORDER BY tenant_id ASC"
        ).fetchall()
        return [row[0] for row in rows]

    def _ensure_schema(self) -> None:
        conn = self._connect()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tools (
                tenant_id TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                handler_ref TEXT NOT NULL,
                data_json TEXT NOT NULL,
                PRIMARY KEY (tenant_id, tool_name)
            )
            """
        )
        conn.commit()


class SQLiteAgentStore(AgentStore):
    """SQLite-backed agent store using upsert semantics.

    For ':memory:' databases a single shared connection is kept alive for the
    lifetime of the store instance; file-based databases use a new connection per
    operation so multiple processes can share the same file safely.
    """

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._db_path = str(db_path)
        self._shared_conn: sqlite3.Connection | None = (
            sqlite3.connect(":memory:", check_same_thread=False)
            if self._db_path == ":memory:"
            else None
        )
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        if self._shared_conn is not None:
            return self._shared_conn
        return sqlite3.connect(self._db_path)

    async def save_agent(self, tenant_id: str, record: PersistedAgentRecord) -> None:
        data = {
            "capability_tags": record.capability_tags,
            "instructions": record.instructions,
            "metadata": record.metadata,
        }
        conn = self._connect()
        conn.execute(
            """
            INSERT INTO agents (tenant_id, agent_id, role, data_json)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(tenant_id, agent_id) DO UPDATE SET
                role=excluded.role,
                data_json=excluded.data_json
            """,
            (tenant_id, record.agent_id, record.role, json.dumps(data)),
        )
        conn.commit()

    async def delete_agent(self, tenant_id: str, agent_id: str) -> None:
        conn = self._connect()
        conn.execute(
            "DELETE FROM agents WHERE tenant_id = ? AND agent_id = ?",
            (tenant_id, agent_id),
        )
        conn.commit()

    async def list_agents(self, tenant_id: str) -> list[PersistedAgentRecord]:
        conn = self._connect()
        rows = conn.execute(
            """
            SELECT agent_id, role, data_json
            FROM agents
            WHERE tenant_id = ?
            ORDER BY agent_id ASC
            """,
            (tenant_id,),
        ).fetchall()
        records = []
        for row in rows:
            agent_id, role, data_json = row
            data = json.loads(data_json)
            records.append(
                PersistedAgentRecord(
                    agent_id=agent_id,
                    role=role,
                    tenant_id=tenant_id,
                    capability_tags=data.get("capability_tags", []),
                    instructions=data.get("instructions", ""),
                    metadata=data.get("metadata", {}),
                )
            )
        return records

    async def list_tenant_ids(self) -> list[str]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT DISTINCT tenant_id FROM agents ORDER BY tenant_id ASC"
        ).fetchall()
        return [row[0] for row in rows]

    def _ensure_schema(self) -> None:
        conn = self._connect()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agents (
                tenant_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                role TEXT NOT NULL,
                data_json TEXT NOT NULL,
                PRIMARY KEY (tenant_id, agent_id)
            )
            """
        )
        conn.commit()


class SQLiteApiKeyStore(ApiKeyStore):
    """SQLite-backed API key store.

    Stores a SHA-256 hash of the actual key — plaintext is never written to disk.
    Supports lookup by hash for authentication and management by key_id.
    For ':memory:' databases a single shared connection is kept alive.
    """

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._db_path = str(db_path)
        self._shared_conn: sqlite3.Connection | None = (
            sqlite3.connect(":memory:", check_same_thread=False)
            if self._db_path == ":memory:"
            else None
        )
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        if self._shared_conn is not None:
            return self._shared_conn
        return sqlite3.connect(self._db_path)

    async def save_key(self, record: ApiKeyRecord) -> None:
        conn = self._connect()
        conn.execute(
            """
            INSERT INTO api_keys (key_id, tenant_id, subject, key_hash, roles_csv, description, enabled, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(key_id) DO UPDATE SET
                tenant_id=excluded.tenant_id,
                subject=excluded.subject,
                key_hash=excluded.key_hash,
                roles_csv=excluded.roles_csv,
                description=excluded.description,
                enabled=excluded.enabled,
                created_at=excluded.created_at
            """,
            (
                record.key_id,
                record.tenant_id,
                record.subject,
                record.key_hash,
                ",".join(record.roles),
                record.description,
                1 if record.enabled else 0,
                record.created_at,
            ),
        )
        conn.commit()

    async def get_key(self, key_id: str) -> ApiKeyRecord | None:
        conn = self._connect()
        row = conn.execute(
            "SELECT key_id, tenant_id, subject, key_hash, roles_csv, description, enabled, created_at "
            "FROM api_keys WHERE key_id = ?",
            (key_id,),
        ).fetchone()
        return self._row_to_record(row) if row else None

    async def lookup_by_hash(self, key_hash: str) -> ApiKeyRecord | None:
        conn = self._connect()
        row = conn.execute(
            "SELECT key_id, tenant_id, subject, key_hash, roles_csv, description, enabled, created_at "
            "FROM api_keys WHERE key_hash = ? AND enabled = 1",
            (key_hash,),
        ).fetchone()
        return self._row_to_record(row) if row else None

    async def delete_key(self, key_id: str) -> None:
        conn = self._connect()
        conn.execute("DELETE FROM api_keys WHERE key_id = ?", (key_id,))
        conn.commit()

    async def list_keys(self, tenant_id: str | None = None) -> list[ApiKeyRecord]:
        conn = self._connect()
        if tenant_id is not None:
            rows = conn.execute(
                "SELECT key_id, tenant_id, subject, key_hash, roles_csv, description, enabled, created_at "
                "FROM api_keys WHERE tenant_id = ? ORDER BY created_at ASC",
                (tenant_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT key_id, tenant_id, subject, key_hash, roles_csv, description, enabled, created_at "
                "FROM api_keys ORDER BY created_at ASC"
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def _row_to_record(self, row: tuple) -> ApiKeyRecord:
        key_id, tenant_id, subject, key_hash, roles_csv, description, enabled, created_at = row
        roles = [r.strip() for r in roles_csv.split(",") if r.strip()] if roles_csv else []
        return ApiKeyRecord(
            key_id=key_id,
            tenant_id=tenant_id,
            subject=subject,
            key_hash=key_hash,
            roles=roles,
            description=description,
            enabled=bool(enabled),
            created_at=created_at,
        )

    def _ensure_schema(self) -> None:
        conn = self._connect()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS api_keys (
                key_id TEXT NOT NULL PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                subject TEXT NOT NULL,
                key_hash TEXT NOT NULL UNIQUE,
                roles_csv TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT ''
            )
            """
        )
        conn.commit()

