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

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Callable, TypeVar

from src.core.session_context import SessionContext
from src.persistence.migrations import SQLiteMigration, apply_sqlite_migrations
from src.persistence.contracts import (
    AgentStore,
    ApiKeyRecord,
    ApiKeyStore,
    CheckpointRecord,
    CheckpointStatus,
    CheckpointStoreContract,
    PersistedAgentRecord,
    PersistedProviderRecord,
    PersistedToolRecord,
    PersistenceIsolationError,
    ProviderStore,
    SessionRecord,
    SessionStore,
    ToolStore,
    ToolPackageManifest,
    ToolValidationResult,
    ToolValidationState,
    ToolVersionRecord,
    ToolVersionStore,
)

_T = TypeVar("_T")


async def _run_blocking(callable_fn: Callable[[], _T]) -> _T:
    """Execute blocking sqlite operations off the event loop."""
    return await asyncio.to_thread(callable_fn)


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
        def _save() -> None:
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

        await _run_blocking(_save)

    async def get_session(self, session_id: str, tenant_id: str = "default") -> SessionRecord | None:
        def _load() -> tuple | None:
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
                return row

        row = await _run_blocking(_load)
        if row is None:
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

    async def count_active_sessions_by_provider(self, provider_id: str) -> int:
        def _count() -> int:
            with sqlite3.connect(self._db_path) as conn:
                row = conn.execute(
                    "SELECT COUNT(1) FROM sessions WHERE provider_id = ? AND state = 'active'",
                    (provider_id,),
                ).fetchone()
            return row[0] if row else 0

        return await _run_blocking(_count)

    async def deactivate_sessions_by_provider(self, provider_id: str) -> int:
        def _deactivate() -> int:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.execute(
                    """
                    UPDATE sessions
                    SET state = 'cancelled'
                    WHERE provider_id = ? AND state = 'active'
                    """,
                    (provider_id,),
                )
                conn.commit()
                return int(cursor.rowcount or 0)

        return await _run_blocking(_deactivate)

    def _ensure_schema(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            apply_sqlite_migrations(
                conn,
                [
                    SQLiteMigration(
                        migration_id="sessions.v1",
                        statements=(
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
                            """,
                        ),
                    )
                ],
            )


class SQLiteCheckpointStore(CheckpointStoreContract):
    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._db_path = str(db_path)
        self._ensure_schema()

    async def save_checkpoint(self, checkpoint: CheckpointRecord) -> None:
        def _save() -> None:
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

        await _run_blocking(_save)

    async def list_checkpoints(self, job_id: str, tenant_id: str = "default") -> list[CheckpointRecord]:
        def _list() -> list[tuple]:
            with sqlite3.connect(self._db_path) as conn:
                return conn.execute(
                    """
                    SELECT tenant_id, job_id, node_id, status, attempt, reason_code, payload_json
                    FROM checkpoints
                    WHERE tenant_id = ? AND job_id = ?
                    ORDER BY node_id ASC
                    """,
                    (tenant_id, job_id),
                ).fetchall()

        rows = await _run_blocking(_list)
        checkpoints = [self._row_to_checkpoint(row) for row in rows]
        for checkpoint in checkpoints:
            _assert_tenant_match(
                stored_tenant_id=checkpoint.tenant_id,
                requested_tenant_id=tenant_id,
                entity_type="checkpoint",
            )
        return checkpoints

    async def get_checkpoint(self, job_id: str, node_id: str, tenant_id: str = "default") -> CheckpointRecord | None:
        def _load() -> tuple | None:
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
                return row

        row = await _run_blocking(_load)
        if row is None:
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
            apply_sqlite_migrations(
                conn,
                [
                    SQLiteMigration(
                        migration_id="checkpoints.v1",
                        statements=(
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
                            """,
                        ),
                    )
                ],
            )

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
        apply_sqlite_migrations(
            conn,
            [
                SQLiteMigration(
                    migration_id="tools.v1",
                    statements=(
                        """
                        CREATE TABLE IF NOT EXISTS tools (
                            tenant_id TEXT NOT NULL,
                            tool_name TEXT NOT NULL,
                            handler_ref TEXT NOT NULL,
                            data_json TEXT NOT NULL,
                            PRIMARY KEY (tenant_id, tool_name)
                        )
                        """,
                    ),
                )
            ],
        )


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
        apply_sqlite_migrations(
            conn,
            [
                SQLiteMigration(
                    migration_id="agents.v1",
                    statements=(
                        """
                        CREATE TABLE IF NOT EXISTS agents (
                            tenant_id TEXT NOT NULL,
                            agent_id TEXT NOT NULL,
                            role TEXT NOT NULL,
                            data_json TEXT NOT NULL,
                            PRIMARY KEY (tenant_id, agent_id)
                        )
                        """,
                    ),
                )
            ],
        )


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
        apply_sqlite_migrations(
            conn,
            [
                SQLiteMigration(
                    migration_id="api_keys.v1",
                    statements=(
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
                        """,
                    ),
                )
            ],
        )


class SQLiteProviderStore(ProviderStore):
    """SQLite-backed provider store for dynamic registration.

    Persists ProviderRecord as a flat row; used for startup hydration.
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

    async def save_provider(self, record: PersistedProviderRecord) -> None:
        conn = self._connect()
        conn.execute(
            """
            INSERT INTO providers (
                provider_id, display_name, adapter_class, enabled, profile, priority,
                endpoint_base_url, endpoint_api_type, auth_type, auth_api_key_env_var,
                model, temperature, max_output_tokens
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(provider_id) DO UPDATE SET
                display_name=excluded.display_name,
                adapter_class=excluded.adapter_class,
                enabled=excluded.enabled,
                profile=excluded.profile,
                priority=excluded.priority,
                endpoint_base_url=excluded.endpoint_base_url,
                endpoint_api_type=excluded.endpoint_api_type,
                auth_type=excluded.auth_type,
                auth_api_key_env_var=excluded.auth_api_key_env_var,
                model=excluded.model,
                temperature=excluded.temperature,
                max_output_tokens=excluded.max_output_tokens
            """,
            (
                record.provider_id,
                record.display_name,
                record.adapter_class,
                1 if record.enabled else 0,
                record.profile,
                record.priority,
                record.endpoint_base_url,
                record.endpoint_api_type,
                record.auth_type,
                record.auth_api_key_env_var,
                record.model,
                record.temperature,
                record.max_output_tokens,
            ),
        )
        conn.commit()

    async def get_provider(self, provider_id: str) -> PersistedProviderRecord | None:
        conn = self._connect()
        row = conn.execute(
            """SELECT provider_id, display_name, adapter_class, enabled, profile, priority,
               endpoint_base_url, endpoint_api_type, auth_type, auth_api_key_env_var,
               model, temperature, max_output_tokens FROM providers WHERE provider_id = ?""",
            (provider_id,),
        ).fetchone()
        return self._row_to_record(row) if row else None

    async def delete_provider(self, provider_id: str) -> None:
        conn = self._connect()
        conn.execute("DELETE FROM providers WHERE provider_id = ?", (provider_id,))
        conn.commit()

    async def list_providers(self) -> list[PersistedProviderRecord]:
        conn = self._connect()
        rows = conn.execute(
            """SELECT provider_id, display_name, adapter_class, enabled, profile, priority,
               endpoint_base_url, endpoint_api_type, auth_type, auth_api_key_env_var,
               model, temperature, max_output_tokens FROM providers ORDER BY provider_id"""
        ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def _row_to_record(self, row: tuple) -> PersistedProviderRecord:
        return PersistedProviderRecord(
            provider_id=row[0],
            display_name=row[1],
            adapter_class=row[2],
            enabled=bool(row[3]),
            profile=row[4],
            priority=row[5],
            endpoint_base_url=row[6],
            endpoint_api_type=row[7],
            auth_type=row[8],
            auth_api_key_env_var=row[9],
            model=row[10],
            temperature=row[11],
            max_output_tokens=row[12],
        )

    def _ensure_schema(self) -> None:
        conn = self._connect()
        apply_sqlite_migrations(
            conn,
            [
                SQLiteMigration(
                    migration_id="providers.v1",
                    statements=(
                        """
                        CREATE TABLE IF NOT EXISTS providers (
                            provider_id TEXT NOT NULL PRIMARY KEY,
                            display_name TEXT NOT NULL,
                            adapter_class TEXT NOT NULL,
                            enabled INTEGER NOT NULL DEFAULT 1,
                            profile TEXT NOT NULL,
                            priority INTEGER NOT NULL,
                            endpoint_base_url TEXT NOT NULL,
                            endpoint_api_type TEXT NOT NULL,
                            auth_type TEXT NOT NULL,
                            auth_api_key_env_var TEXT NOT NULL,
                            model TEXT NOT NULL,
                            temperature REAL NOT NULL DEFAULT 0.2,
                            max_output_tokens INTEGER NOT NULL DEFAULT 1500
                        )
                        """,
                    ),
                )
            ],
        )



class SQLiteToolVersionStore(ToolVersionStore):
    """SQLite-backed store for tenant tool package versions and validation status."""

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

    async def save_tool_version(self, record: ToolVersionRecord) -> None:
        manifest = {
            "tool_name": record.manifest.tool_name,
            "version": record.manifest.version,
            "description": record.manifest.description,
            "input_schema": record.manifest.input_schema,
            "timeout_ms": record.manifest.timeout_ms,
            "risk_tier": record.manifest.risk_tier,
            "entry_file": record.manifest.entry_file,
            "entrypoint": record.manifest.entrypoint,
            "requirements": record.manifest.requirements,
            "metadata": record.manifest.metadata,
        }
        validation = {
            "tool_name": record.validation.tool_name if record.validation else record.tool_name,
            "version": record.validation.version if record.validation else record.version,
            "state": (record.validation.state.value if record.validation else ToolValidationState.PENDING.value),
            "errors": record.validation.errors if record.validation else [],
            "warnings": record.validation.warnings if record.validation else [],
            "normalized_schema_hash": (record.validation.normalized_schema_hash if record.validation else ""),
        }
        conn = self._connect()
        conn.execute(
            """
            INSERT INTO tool_versions (
                tenant_id, tool_name, version, manifest_json, validation_json, package_ref, active, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(tenant_id, tool_name, version) DO UPDATE SET
                manifest_json=excluded.manifest_json,
                validation_json=excluded.validation_json,
                package_ref=excluded.package_ref,
                active=excluded.active,
                created_at=excluded.created_at
            """,
            (
                record.tenant_id,
                record.tool_name,
                record.version,
                json.dumps(manifest),
                json.dumps(validation),
                record.package_ref,
                1 if record.active else 0,
                record.created_at,
            ),
        )
        conn.commit()

    async def get_tool_version(self, tenant_id: str, tool_name: str, version: str) -> ToolVersionRecord | None:
        conn = self._connect()
        row = conn.execute(
            """
            SELECT tenant_id, tool_name, version, manifest_json, validation_json, package_ref, active, created_at
            FROM tool_versions
            WHERE tenant_id = ? AND tool_name = ? AND version = ?
            """,
            (tenant_id, tool_name, version),
        ).fetchone()
        return self._row_to_record(row) if row else None

    async def list_tool_versions(self, tenant_id: str, tool_name: str) -> list[ToolVersionRecord]:
        conn = self._connect()
        rows = conn.execute(
            """
            SELECT tenant_id, tool_name, version, manifest_json, validation_json, package_ref, active, created_at
            FROM tool_versions
            WHERE tenant_id = ? AND tool_name = ?
            ORDER BY version DESC
            """,
            (tenant_id, tool_name),
        ).fetchall()
        return [self._row_to_record(row) for row in rows]

    async def set_active_tool_version(self, tenant_id: str, tool_name: str, version: str) -> None:
        conn = self._connect()
        conn.execute(
            "UPDATE tool_versions SET active = 0 WHERE tenant_id = ? AND tool_name = ?",
            (tenant_id, tool_name),
        )
        conn.execute(
            """
            UPDATE tool_versions
            SET active = 1
            WHERE tenant_id = ? AND tool_name = ? AND version = ?
            """,
            (tenant_id, tool_name, version),
        )
        conn.commit()

    async def get_active_tool_version(self, tenant_id: str, tool_name: str) -> ToolVersionRecord | None:
        conn = self._connect()
        row = conn.execute(
            """
            SELECT tenant_id, tool_name, version, manifest_json, validation_json, package_ref, active, created_at
            FROM tool_versions
            WHERE tenant_id = ? AND tool_name = ? AND active = 1
            LIMIT 1
            """,
            (tenant_id, tool_name),
        ).fetchone()
        return self._row_to_record(row) if row else None

    async def clear_active_tool_version(self, tenant_id: str, tool_name: str) -> None:
        conn = self._connect()
        conn.execute(
            "UPDATE tool_versions SET active = 0 WHERE tenant_id = ? AND tool_name = ?",
            (tenant_id, tool_name),
        )
        conn.commit()

    async def delete_tool_version(self, tenant_id: str, tool_name: str, version: str) -> None:
        conn = self._connect()
        conn.execute(
            """
            DELETE FROM tool_versions
            WHERE tenant_id = ? AND tool_name = ? AND version = ?
            """,
            (tenant_id, tool_name, version),
        )
        conn.commit()

    async def list_tenant_ids(self) -> list[str]:
        conn = self._connect()
        rows = conn.execute(
            """
            SELECT DISTINCT tenant_id
            FROM tool_versions
            ORDER BY tenant_id
            """
        ).fetchall()
        return [str(row[0]) for row in rows]

    async def list_active_tool_versions(self, tenant_id: str) -> list[ToolVersionRecord]:
        conn = self._connect()
        rows = conn.execute(
            """
            SELECT tenant_id, tool_name, version, manifest_json, validation_json, package_ref, active, created_at
            FROM tool_versions
            WHERE tenant_id = ? AND active = 1
            ORDER BY tool_name
            """,
            (tenant_id,),
        ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def _row_to_record(self, row: tuple) -> ToolVersionRecord:
        tenant_id, tool_name, version, manifest_json, validation_json, package_ref, active, created_at = row
        manifest_data = json.loads(manifest_json)
        validation_data = json.loads(validation_json)
        manifest = ToolPackageManifest(
            tool_name=manifest_data.get("tool_name", tool_name),
            version=manifest_data.get("version", version),
            description=manifest_data.get("description", ""),
            input_schema=manifest_data.get("input_schema", {}),
            timeout_ms=manifest_data.get("timeout_ms", 30000),
            risk_tier=manifest_data.get("risk_tier", "low"),
            entry_file=manifest_data.get("entry_file", "handler.py"),
            entrypoint=manifest_data.get("entrypoint", "run"),
            requirements=manifest_data.get("requirements", []),
            metadata=manifest_data.get("metadata", {}),
        )
        validation = ToolValidationResult(
            tool_name=validation_data.get("tool_name", tool_name),
            version=validation_data.get("version", version),
            state=ToolValidationState(validation_data.get("state", ToolValidationState.PENDING.value)),
            errors=validation_data.get("errors", []),
            warnings=validation_data.get("warnings", []),
            normalized_schema_hash=validation_data.get("normalized_schema_hash", ""),
        )
        return ToolVersionRecord(
            tenant_id=tenant_id,
            tool_name=tool_name,
            version=version,
            manifest=manifest,
            validation=validation,
            package_ref=package_ref,
            active=bool(active),
            created_at=created_at,
        )

    def _ensure_schema(self) -> None:
        conn = self._connect()
        apply_sqlite_migrations(
            conn,
            [
                SQLiteMigration(
                    migration_id="tool_versions.v1",
                    statements=(
                        """
                        CREATE TABLE IF NOT EXISTS tool_versions (
                            tenant_id TEXT NOT NULL,
                            tool_name TEXT NOT NULL,
                            version TEXT NOT NULL,
                            manifest_json TEXT NOT NULL,
                            validation_json TEXT NOT NULL,
                            package_ref TEXT NOT NULL DEFAULT '',
                            active INTEGER NOT NULL DEFAULT 0,
                            created_at TEXT NOT NULL DEFAULT '',
                            PRIMARY KEY (tenant_id, tool_name, version)
                        )
                        """,
                    ),
                )
            ],
        )


