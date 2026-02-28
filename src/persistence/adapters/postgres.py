"""
File: postgres.py
Path: src/persistence/adapters/postgres.py
Role: Postgres-style persistence adapters over an injectable storage driver.
Used By:
 - tests/integration/test_persistence_adapter_parity.py
Depends On:
 - src/persistence/contracts.py
 - src/core/session_context.py
Notes:
 - Driver injection keeps adapter contract testable without requiring a live database.
"""

from __future__ import annotations

from dataclasses import replace

from src.persistence.contracts import CheckpointRecord, CheckpointStoreContract, SessionRecord, SessionStore


class InMemoryPostgresDriver:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionRecord] = {}
        self._checkpoints: dict[tuple[str, str], CheckpointRecord] = {}

    def save_session(self, record: SessionRecord) -> None:
        self._sessions[record.session.session_id] = replace(
            record,
            session=replace(record.session, metadata=dict(record.session.metadata)),
            data=dict(record.data),
        )

    def get_session(self, session_id: str) -> SessionRecord | None:
        record = self._sessions.get(session_id)
        if record is None:
            return None
        return replace(
            record,
            session=replace(record.session, metadata=dict(record.session.metadata)),
            data=dict(record.data),
        )

    def save_checkpoint(self, checkpoint: CheckpointRecord) -> None:
        self._checkpoints[(checkpoint.job_id, checkpoint.node_id)] = replace(
            checkpoint,
            payload=dict(checkpoint.payload),
        )

    def list_checkpoints(self, job_id: str) -> list[CheckpointRecord]:
        rows = [
            replace(record, payload=dict(record.payload))
            for (stored_job_id, _), record in self._checkpoints.items()
            if stored_job_id == job_id
        ]
        return sorted(rows, key=lambda item: item.node_id)

    def get_checkpoint(self, job_id: str, node_id: str) -> CheckpointRecord | None:
        record = self._checkpoints.get((job_id, node_id))
        if record is None:
            return None
        return replace(record, payload=dict(record.payload))


class PostgresSessionStore(SessionStore):
    def __init__(self, driver: InMemoryPostgresDriver | None = None) -> None:
        self._driver = driver or InMemoryPostgresDriver()

    async def save_session(self, record: SessionRecord) -> None:
        self._driver.save_session(record)

    async def get_session(self, session_id: str) -> SessionRecord | None:
        return self._driver.get_session(session_id)


class PostgresCheckpointStore(CheckpointStoreContract):
    def __init__(self, driver: InMemoryPostgresDriver | None = None) -> None:
        self._driver = driver or InMemoryPostgresDriver()

    async def save_checkpoint(self, checkpoint: CheckpointRecord) -> None:
        self._driver.save_checkpoint(checkpoint)

    async def list_checkpoints(self, job_id: str) -> list[CheckpointRecord]:
        return self._driver.list_checkpoints(job_id)

    async def get_checkpoint(self, job_id: str, node_id: str) -> CheckpointRecord | None:
        return self._driver.get_checkpoint(job_id, node_id)


def build_postgres_stores(
    driver: InMemoryPostgresDriver | None = None,
) -> tuple[PostgresSessionStore, PostgresCheckpointStore]:
    resolved_driver = driver or InMemoryPostgresDriver()
    return PostgresSessionStore(driver=resolved_driver), PostgresCheckpointStore(driver=resolved_driver)
