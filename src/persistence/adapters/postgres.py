"""
File: postgres.py
Path: src/persistence/adapters/postgres.py
Role: Postgres-style persistence adapters over an injectable storage driver.
Used By:
 - tests/modules/core/test_persistence_adapter_parity.py
Depends On:
 - src/persistence/contracts.py
 - src/core/session_context.py
Notes:
 - Driver injection keeps adapter contract testable without requiring a live database.
"""

from __future__ import annotations

from dataclasses import replace

from src.persistence.contracts import (
    CheckpointRecord,
    CheckpointStoreContract,
    PersistenceIsolationError,
    SessionRecord,
    SessionStore,
)


class InMemoryPostgresDriver:
    def __init__(self) -> None:
        self._sessions: dict[tuple[str, str], SessionRecord] = {}
        self._checkpoints: dict[tuple[str, str, str], CheckpointRecord] = {}

    def save_session(self, record: SessionRecord) -> None:
        self._sessions[(record.tenant_id, record.session.session_id)] = replace(
            record,
            session=replace(record.session, metadata=dict(record.session.metadata)),
            data=dict(record.data),
        )

    def get_session(self, session_id: str, tenant_id: str = "default") -> SessionRecord | None:
        record = self._sessions.get((tenant_id, session_id))
        if record is None:
            for (stored_tenant_id, stored_session_id), _ in self._sessions.items():
                if stored_session_id == session_id:
                    raise PersistenceIsolationError(
                        reason_code="PERSISTENCE_TENANT_ISOLATION_VIOLATION",
                        message="session belongs to a different tenant",
                        tenant_id=stored_tenant_id,
                        requested_tenant_id=tenant_id,
                    )
            return None
        if record.tenant_id != tenant_id:
            raise PersistenceIsolationError(
                reason_code="PERSISTENCE_TENANT_ISOLATION_VIOLATION",
                message="session belongs to a different tenant",
                tenant_id=record.tenant_id,
                requested_tenant_id=tenant_id,
            )
        return replace(
            record,
            session=replace(record.session, metadata=dict(record.session.metadata)),
            data=dict(record.data),
        )

    def count_active_sessions_by_provider(self, provider_id: str) -> int:
        return sum(
            1
            for r in self._sessions.values()
            if r.session.provider_id == provider_id and r.state == "active"
        )

    def save_checkpoint(self, checkpoint: CheckpointRecord) -> None:
        self._checkpoints[(checkpoint.tenant_id, checkpoint.job_id, checkpoint.node_id)] = replace(
            checkpoint,
            payload=dict(checkpoint.payload),
        )

    def list_checkpoints(self, job_id: str, tenant_id: str = "default") -> list[CheckpointRecord]:
        rows = [
            replace(record, payload=dict(record.payload))
            for (stored_tenant_id, stored_job_id, _), record in self._checkpoints.items()
            if stored_tenant_id == tenant_id and stored_job_id == job_id
        ]
        return sorted(rows, key=lambda item: item.node_id)

    def get_checkpoint(self, job_id: str, node_id: str, tenant_id: str = "default") -> CheckpointRecord | None:
        record = self._checkpoints.get((tenant_id, job_id, node_id))
        if record is None:
            for (stored_tenant_id, stored_job_id, stored_node_id), _ in self._checkpoints.items():
                if stored_job_id == job_id and stored_node_id == node_id:
                    raise PersistenceIsolationError(
                        reason_code="PERSISTENCE_TENANT_ISOLATION_VIOLATION",
                        message="checkpoint belongs to a different tenant",
                        tenant_id=stored_tenant_id,
                        requested_tenant_id=tenant_id,
                    )
            return None
        if record.tenant_id != tenant_id:
            raise PersistenceIsolationError(
                reason_code="PERSISTENCE_TENANT_ISOLATION_VIOLATION",
                message="checkpoint belongs to a different tenant",
                tenant_id=record.tenant_id,
                requested_tenant_id=tenant_id,
            )
        return replace(record, payload=dict(record.payload))


class PostgresSessionStore(SessionStore):
    def __init__(self, driver: InMemoryPostgresDriver | None = None) -> None:
        self._driver = driver or InMemoryPostgresDriver()

    async def save_session(self, record: SessionRecord) -> None:
        self._driver.save_session(record)

    async def get_session(self, session_id: str, tenant_id: str = "default") -> SessionRecord | None:
        return self._driver.get_session(session_id, tenant_id=tenant_id)

    async def count_active_sessions_by_provider(self, provider_id: str) -> int:
        return self._driver.count_active_sessions_by_provider(provider_id)


class PostgresCheckpointStore(CheckpointStoreContract):
    def __init__(self, driver: InMemoryPostgresDriver | None = None) -> None:
        self._driver = driver or InMemoryPostgresDriver()

    async def save_checkpoint(self, checkpoint: CheckpointRecord) -> None:
        self._driver.save_checkpoint(checkpoint)

    async def list_checkpoints(self, job_id: str, tenant_id: str = "default") -> list[CheckpointRecord]:
        return self._driver.list_checkpoints(job_id, tenant_id=tenant_id)

    async def get_checkpoint(self, job_id: str, node_id: str, tenant_id: str = "default") -> CheckpointRecord | None:
        return self._driver.get_checkpoint(job_id, node_id, tenant_id=tenant_id)


def build_postgres_stores(
    driver: InMemoryPostgresDriver | None = None,
) -> tuple[PostgresSessionStore, PostgresCheckpointStore]:
    resolved_driver = driver or InMemoryPostgresDriver()
    return PostgresSessionStore(driver=resolved_driver), PostgresCheckpointStore(driver=resolved_driver)
