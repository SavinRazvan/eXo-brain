"""
File: test_tenant_scoped_session_checkpoint.py
Path: tests/modules/persistence/test_tenant_scoped_session_checkpoint.py
Role: Verifies tenant-scoped isolation for session/checkpoint persistence adapters.
Used By:
 - pytest
Depends On:
 - src/persistence/adapters/sqlite.py
 - src/persistence/adapters/postgres.py
 - src/persistence/contracts.py
 - src/core/session_context.py
Notes:
 - Ensures same identifiers across tenants are isolated and cross-tenant reads are rejected.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import time

import pytest

from src.core.session_context import SessionContext
from src.persistence.adapters.postgres import build_postgres_stores
from src.persistence.adapters.sqlite import SQLiteCheckpointStore, SQLiteSessionStore
from src.persistence.contracts import CheckpointRecord, CheckpointStatus, PersistenceIsolationError, SessionRecord


def _session_record(*, session_id: str, tenant_id: str, state: str) -> SessionRecord:
    return SessionRecord(
        session=SessionContext(
            session_id=session_id,
            run_id=f"run_{tenant_id}",
            job_id="job_1",
            task_id="task_1",
            agent_id="agent_1",
            provider_id="openai",
            correlation_id=f"corr_{tenant_id}",
            metadata={"tenant_id": tenant_id},
        ),
        tenant_id=tenant_id,
        state=state,
        data={"tenant": tenant_id},
    )


def _checkpoint_record(*, node_id: str, tenant_id: str, status: CheckpointStatus) -> CheckpointRecord:
    return CheckpointRecord(
        job_id="job_1",
        node_id=node_id,
        tenant_id=tenant_id,
        status=status,
        attempt=1,
        payload={"tenant": tenant_id},
    )


def test_sqlite_session_and_checkpoint_stores_enforce_tenant_isolation(tmp_path: Path) -> None:
    async def scenario() -> None:
        session_store = SQLiteSessionStore(db_path=tmp_path / "tenant_sessions.db")
        checkpoint_store = SQLiteCheckpointStore(db_path=tmp_path / "tenant_checkpoints.db")

        await session_store.save_session(_session_record(session_id="sess_1", tenant_id="tenant_a", state="active"))
        await session_store.save_session(_session_record(session_id="sess_1", tenant_id="tenant_b", state="paused"))
        await checkpoint_store.save_checkpoint(
            _checkpoint_record(node_id="node_1", tenant_id="tenant_a", status=CheckpointStatus.RUNNING)
        )
        await checkpoint_store.save_checkpoint(
            _checkpoint_record(node_id="node_1", tenant_id="tenant_b", status=CheckpointStatus.COMPLETED)
        )

        tenant_a_session = await session_store.get_session("sess_1", tenant_id="tenant_a")
        tenant_b_session = await session_store.get_session("sess_1", tenant_id="tenant_b")
        assert tenant_a_session is not None and tenant_a_session.state == "active"
        assert tenant_b_session is not None and tenant_b_session.state == "paused"

        tenant_a_checkpoint = await checkpoint_store.get_checkpoint("job_1", "node_1", tenant_id="tenant_a")
        tenant_b_checkpoint = await checkpoint_store.get_checkpoint("job_1", "node_1", tenant_id="tenant_b")
        assert tenant_a_checkpoint is not None and tenant_a_checkpoint.status == CheckpointStatus.RUNNING
        assert tenant_b_checkpoint is not None and tenant_b_checkpoint.status == CheckpointStatus.COMPLETED

        with pytest.raises(PersistenceIsolationError):
            await session_store.get_session("sess_1", tenant_id="tenant_c")

        with pytest.raises(PersistenceIsolationError):
            await checkpoint_store.get_checkpoint("job_1", "node_1", tenant_id="tenant_c")

    asyncio.run(scenario())


def test_postgres_session_and_checkpoint_stores_enforce_tenant_isolation() -> None:
    async def scenario() -> None:
        session_store, checkpoint_store = build_postgres_stores()

        await session_store.save_session(_session_record(session_id="sess_1", tenant_id="tenant_a", state="active"))
        await session_store.save_session(_session_record(session_id="sess_1", tenant_id="tenant_b", state="paused"))
        await checkpoint_store.save_checkpoint(
            _checkpoint_record(node_id="node_1", tenant_id="tenant_a", status=CheckpointStatus.RUNNING)
        )
        await checkpoint_store.save_checkpoint(
            _checkpoint_record(node_id="node_1", tenant_id="tenant_b", status=CheckpointStatus.COMPLETED)
        )

        tenant_a_session = await session_store.get_session("sess_1", tenant_id="tenant_a")
        tenant_b_session = await session_store.get_session("sess_1", tenant_id="tenant_b")
        assert tenant_a_session is not None and tenant_a_session.state == "active"
        assert tenant_b_session is not None and tenant_b_session.state == "paused"

        tenant_a_checkpoint = await checkpoint_store.get_checkpoint("job_1", "node_1", tenant_id="tenant_a")
        tenant_b_checkpoint = await checkpoint_store.get_checkpoint("job_1", "node_1", tenant_id="tenant_b")
        assert tenant_a_checkpoint is not None and tenant_a_checkpoint.status == CheckpointStatus.RUNNING
        assert tenant_b_checkpoint is not None and tenant_b_checkpoint.status == CheckpointStatus.COMPLETED

        with pytest.raises(PersistenceIsolationError):
            await session_store.get_session("sess_1", tenant_id="tenant_c")

        with pytest.raises(PersistenceIsolationError):
            await checkpoint_store.get_checkpoint("job_1", "node_1", tenant_id="tenant_c")

    asyncio.run(scenario())


def test_sqlite_session_checkpoint_calls_do_not_block_event_loop(tmp_path: Path, monkeypatch) -> None:
    from src.persistence.adapters import sqlite as sqlite_module

    original_connect = sqlite_module.sqlite3.connect

    def slow_connect(*args, **kwargs):
        time.sleep(0.03)
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(sqlite_module.sqlite3, "connect", slow_connect)

    async def scenario() -> None:
        session_store = SQLiteSessionStore(db_path=tmp_path / "async_sessions.db")
        checkpoint_store = SQLiteCheckpointStore(db_path=tmp_path / "async_checkpoints.db")
        ticks = 0
        done = asyncio.Event()

        async def ticker() -> None:
            nonlocal ticks
            while not done.is_set():
                ticks += 1
                await asyncio.sleep(0.005)

        tick_task = asyncio.create_task(ticker())
        await session_store.save_session(_session_record(session_id="sess_async", tenant_id="tenant_a", state="active"))
        await checkpoint_store.save_checkpoint(
            _checkpoint_record(node_id="node_async", tenant_id="tenant_a", status=CheckpointStatus.RUNNING)
        )
        _ = await session_store.get_session("sess_async", tenant_id="tenant_a")
        _ = await checkpoint_store.get_checkpoint("job_1", "node_async", tenant_id="tenant_a")
        done.set()
        await tick_task

        # If sqlite calls run on the loop thread, ticker barely advances.
        assert ticks >= 4

    asyncio.run(scenario())
