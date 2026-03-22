"""
File: test_persistence_adapter_parity.py
Path: tests/modules/core/test_persistence_adapter_parity.py
Role: Parity tests for sqlite and postgres persistence adapter behaviors.
Used By:
 - pytest
Depends On:
 - src/persistence/adapters/sqlite.py
 - src/persistence/adapters/postgres.py
 - src/persistence/contracts.py
 - src/core/session_context.py
Notes:
 - Ensures both adapters satisfy the same contract semantics for save/get/list operations.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path

import pytest

from src.core.session_context import SessionContext
from src.persistence.adapters.postgres import InMemoryPostgresDriver, build_postgres_stores
from src.persistence.adapters.sqlite import SQLiteCheckpointStore, SQLiteSessionStore
from src.persistence.contracts import CheckpointRecord, CheckpointStatus, PersistenceIsolationError, SessionRecord


def _sample_session_record(session_id: str = "sess_1") -> SessionRecord:
    return SessionRecord(
        session=SessionContext(
            session_id=session_id,
            run_id="run_1",
            job_id="job_1",
            task_id="task_1",
            agent_id="agent_1",
            provider_id="openai",
            correlation_id="corr_1",
            metadata={"tenant": "acme"},
        ),
        state="active",
        data={"step": "initialized"},
    )


def _sample_checkpoint(node_id: str = "node_1") -> CheckpointRecord:
    return CheckpointRecord(
        job_id="job_1",
        node_id=node_id,
        status=CheckpointStatus.RUNNING,
        attempt=2,
        reason_code="",
        payload={"progress": 50},
    )


def test_sqlite_and_postgres_session_store_parity(tmp_path: Path) -> None:
    async def scenario() -> None:
        sqlite_store = SQLiteSessionStore(db_path=tmp_path / "sessions.db")
        postgres_store, _ = build_postgres_stores()
        record = _sample_session_record()

        await sqlite_store.save_session(record)
        await postgres_store.save_session(record)

        sqlite_result = await sqlite_store.get_session(record.session.session_id)
        postgres_result = await postgres_store.get_session(record.session.session_id)

        assert sqlite_result is not None
        assert postgres_result is not None
        assert sqlite_result.state == postgres_result.state == "active"
        assert sqlite_result.session.provider_id == postgres_result.session.provider_id == "openai"
        assert sqlite_result.data == postgres_result.data == {"step": "initialized"}

    asyncio.run(scenario())


def test_persistence_isolation_error_str() -> None:
    err = PersistenceIsolationError(
        reason_code="PERSISTENCE_TENANT_ISOLATION_VIOLATION",
        message="cross",
        tenant_id="t_a",
        requested_tenant_id="t_b",
    )
    assert "PERSISTENCE_TENANT_ISOLATION_VIOLATION" in str(err)
    assert "cross" in str(err)


def test_postgres_session_store_raises_when_session_belongs_to_other_tenant() -> None:
    async def scenario() -> None:
        driver = InMemoryPostgresDriver()
        store, _ = build_postgres_stores(driver=driver)
        record = _sample_session_record()
        await store.save_session(record)
        with pytest.raises(PersistenceIsolationError):
            await store.get_session(record.session.session_id, tenant_id="other_tenant")

    asyncio.run(scenario())


def test_postgres_session_store_counts_active_sessions_by_provider() -> None:
    async def scenario() -> None:
        store, _ = build_postgres_stores()
        record = _sample_session_record()
        await store.save_session(record)
        assert await store.count_active_sessions_by_provider("openai") == 1
        assert await store.count_active_sessions_by_provider("missing") == 0

    asyncio.run(scenario())


def test_postgres_driver_detects_session_tenant_mismatch_on_key_collision() -> None:
    driver = InMemoryPostgresDriver()
    record = _sample_session_record()
    driver.save_session(record)
    key = (record.tenant_id, record.session.session_id)
    driver._sessions[key] = replace(record, tenant_id="mismatch")
    with pytest.raises(PersistenceIsolationError):
        driver.get_session(record.session.session_id, tenant_id=record.tenant_id)


def test_postgres_driver_returns_none_for_unknown_session() -> None:
    driver = InMemoryPostgresDriver()
    assert driver.get_session("missing", tenant_id="default") is None


def test_postgres_driver_returns_none_for_unknown_checkpoint() -> None:
    driver = InMemoryPostgresDriver()
    assert driver.get_checkpoint("job_x", "node_y", tenant_id="default") is None


def test_postgres_driver_detects_checkpoint_tenant_mismatch_on_key_collision() -> None:
    driver = InMemoryPostgresDriver()
    checkpoint = _sample_checkpoint()
    driver.save_checkpoint(checkpoint)
    key = (checkpoint.tenant_id, checkpoint.job_id, checkpoint.node_id)
    driver._checkpoints[key] = replace(checkpoint, tenant_id="mismatch")
    with pytest.raises(PersistenceIsolationError):
        driver.get_checkpoint(checkpoint.job_id, checkpoint.node_id, tenant_id=checkpoint.tenant_id)


def test_postgres_checkpoint_store_raises_when_checkpoint_belongs_to_other_tenant() -> None:
    async def scenario() -> None:
        driver = InMemoryPostgresDriver()
        _, store = build_postgres_stores(driver=driver)
        checkpoint = _sample_checkpoint()
        await store.save_checkpoint(checkpoint)
        with pytest.raises(PersistenceIsolationError):
            await store.get_checkpoint(checkpoint.job_id, checkpoint.node_id, tenant_id="other_tenant")

    asyncio.run(scenario())


def test_sqlite_and_postgres_checkpoint_store_parity(tmp_path: Path) -> None:
    async def scenario() -> None:
        sqlite_store = SQLiteCheckpointStore(db_path=tmp_path / "checkpoints.db")
        _, postgres_store = build_postgres_stores()
        first = _sample_checkpoint(node_id="node_1")
        second = _sample_checkpoint(node_id="node_2")

        await sqlite_store.save_checkpoint(first)
        await sqlite_store.save_checkpoint(second)
        await postgres_store.save_checkpoint(first)
        await postgres_store.save_checkpoint(second)

        sqlite_list = await sqlite_store.list_checkpoints("job_1")
        postgres_list = await postgres_store.list_checkpoints("job_1")

        assert [item.node_id for item in sqlite_list] == [item.node_id for item in postgres_list] == ["node_1", "node_2"]

        sqlite_checkpoint = await sqlite_store.get_checkpoint("job_1", "node_2")
        postgres_checkpoint = await postgres_store.get_checkpoint("job_1", "node_2")
        assert sqlite_checkpoint is not None
        assert postgres_checkpoint is not None
        assert sqlite_checkpoint.attempt == postgres_checkpoint.attempt == 2
        assert sqlite_checkpoint.status == postgres_checkpoint.status == CheckpointStatus.RUNNING

    asyncio.run(scenario())
