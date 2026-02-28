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
from pathlib import Path

from src.core.session_context import SessionContext
from src.persistence.adapters.postgres import build_postgres_stores
from src.persistence.adapters.sqlite import SQLiteCheckpointStore, SQLiteSessionStore
from src.persistence.contracts import CheckpointRecord, CheckpointStatus, SessionRecord


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
