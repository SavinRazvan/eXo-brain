"""
File: test_session_store.py
Path: tests/unit/test_session_store.py
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
