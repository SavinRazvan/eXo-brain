"""
File: test_session_store.py
Path: tests/modules/core/test_session_store.py
Role: Unit tests for in-memory session store contract behavior.
Used By:
 - pytest
Depends On:
 - src/core/session_store.py
 - src/core/session_context.py
 - src/persistence/contracts.py
Notes:
 - Confirms save/load semantics and defensive copy behavior.
"""

from __future__ import annotations

import asyncio

from src.core.session_context import SessionContext
from src.core.session_store import InMemorySessionStore
from src.persistence.contracts import SessionRecord


def test_in_memory_session_store_save_and_get() -> None:
    async def scenario() -> None:
        store = InMemorySessionStore()
        record = SessionRecord(
            session=SessionContext(
                session_id="sess_1",
                run_id="run_1",
                job_id="job_1",
                task_id="task_1",
                agent_id="agent_1",
                provider_id="openai",
                correlation_id="corr_1",
                metadata={"tenant": "acme"},
            ),
            state="active",
            data={"turn": 1},
        )
        await store.save_session(record)
        loaded = await store.get_session("sess_1")

        assert loaded is not None
        assert loaded.state == "active"
        assert loaded.data == {"turn": 1}
        assert loaded.session.provider_id == "openai"

    asyncio.run(scenario())


def test_in_memory_session_store_returns_copy() -> None:
    async def scenario() -> None:
        store = InMemorySessionStore()
        record = SessionRecord(
            session=SessionContext(
                session_id="sess_copy",
                run_id="run_1",
                job_id="job_1",
                task_id="task_1",
                agent_id="agent_1",
                metadata={"tenant": "acme"},
            ),
            data={"counter": 1},
        )
        await store.save_session(record)
        loaded = await store.get_session("sess_copy")
        assert loaded is not None
        loaded.data["counter"] = 2
        loaded_again = await store.get_session("sess_copy")
        assert loaded_again is not None
        assert loaded_again.data["counter"] == 1

    asyncio.run(scenario())


def test_in_memory_session_store_returns_none_for_unknown_session() -> None:
    async def scenario() -> None:
        store = InMemorySessionStore()
        loaded = await store.get_session("missing", tenant_id="tenant-404")
        assert loaded is None

    asyncio.run(scenario())


def test_in_memory_session_store_provider_counts_and_deactivate() -> None:
    async def scenario() -> None:
        store = InMemorySessionStore()
        active_openai = SessionRecord(
            session=SessionContext(
                session_id="sess_openai_active",
                run_id="run_1",
                job_id="job_1",
                task_id="task_1",
                agent_id="agent_1",
                provider_id="openai",
                correlation_id="corr_1",
            ),
            state="active",
            data={"turn": 1},
            tenant_id="t1",
        )
        cancelled_openai = SessionRecord(
            session=SessionContext(
                session_id="sess_openai_cancelled",
                run_id="run_2",
                job_id="job_2",
                task_id="task_2",
                agent_id="agent_2",
                provider_id="openai",
                correlation_id="corr_2",
            ),
            state="cancelled",
            data={"turn": 2},
            tenant_id="t2",
        )
        active_other = SessionRecord(
            session=SessionContext(
                session_id="sess_other_active",
                run_id="run_3",
                job_id="job_3",
                task_id="task_3",
                agent_id="agent_3",
                provider_id="custom",
                correlation_id="corr_3",
            ),
            state="active",
            data={"turn": 3},
            tenant_id="t3",
        )
        await store.save_session(active_openai)
        await store.save_session(cancelled_openai)
        await store.save_session(active_other)

        assert await store.count_active_sessions_by_provider("openai") == 1
        assert await store.count_active_sessions_by_provider("custom") == 1
        assert await store.count_active_sessions_by_provider("missing") == 0

        changed = await store.deactivate_sessions_by_provider("openai")
        assert changed == 1
        assert await store.count_active_sessions_by_provider("openai") == 0

        session_after = await store.get_session("sess_openai_active", tenant_id="t1")
        assert session_after is not None
        assert session_after.state == "cancelled"

        changed_custom = await store.deactivate_sessions_by_provider("custom")
        assert changed_custom == 1
        changed_missing = await store.deactivate_sessions_by_provider("missing")
        assert changed_missing == 0

    asyncio.run(scenario())
