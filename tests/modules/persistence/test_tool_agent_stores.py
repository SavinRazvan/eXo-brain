"""
File: test_tool_agent_stores.py
Path: tests/modules/persistence/test_tool_agent_stores.py
Role: Unit tests for SQLiteToolStore and SQLiteAgentStore — contract, upsert, delete, isolation.
Used By:
 - pytest
Depends On:
 - src/persistence/adapters/sqlite.py
 - src/persistence/contracts.py
Notes:
 - All tests use in-memory SQLite (':memory:') for speed and isolation.
 - Covers happy path, delete, upsert idempotency, and tenant isolation.
"""

from __future__ import annotations

import asyncio

import pytest

from src.persistence.adapters.sqlite import SQLiteAgentStore, SQLiteToolStore
from src.persistence.contracts import PersistedAgentRecord, PersistedToolRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tool(name: str = "my_tool", tenant_id: str = "t1") -> PersistedToolRecord:
    return PersistedToolRecord(
        name=name,
        handler_ref="math:sqrt",
        tenant_id=tenant_id,
        risk_tier="low",
        is_state_changing=False,
        timeout_ms=5000,
        description="A test tool",
        parameters_schema={"type": "object"},
        metadata={"handler_ref": "math:sqrt"},
    )


def _agent(agent_id: str = "agent-1", tenant_id: str = "t1") -> PersistedAgentRecord:
    return PersistedAgentRecord(
        agent_id=agent_id,
        role="assistant",
        tenant_id=tenant_id,
        capability_tags=["tool_use"],
        instructions="Be helpful",
        metadata={"model": "gpt-4o-mini"},
    )


# ---------------------------------------------------------------------------
# SQLiteToolStore
# ---------------------------------------------------------------------------


def test_tool_store_save_and_list() -> None:
    store = SQLiteToolStore(":memory:")

    async def run() -> None:
        await store.save_tool("t1", _tool("tool_a", "t1"))
        await store.save_tool("t1", _tool("tool_b", "t1"))
        results = await store.list_tools("t1")
        names = [r.name for r in results]
        assert sorted(names) == ["tool_a", "tool_b"]

    asyncio.run(run())


def test_tool_store_list_empty_tenant() -> None:
    store = SQLiteToolStore(":memory:")

    async def run() -> None:
        results = await store.list_tools("unknown")
        assert results == []

    asyncio.run(run())


def test_tool_store_upsert_overwrites() -> None:
    store = SQLiteToolStore(":memory:")

    async def run() -> None:
        rec = _tool("my_tool", "t1")
        await store.save_tool("t1", rec)

        updated = PersistedToolRecord(
            name="my_tool",
            handler_ref="os.path:join",
            tenant_id="t1",
            risk_tier="medium",
            is_state_changing=True,
            timeout_ms=9999,
            description="Updated",
            parameters_schema={},
            metadata={"handler_ref": "os.path:join"},
        )
        await store.save_tool("t1", updated)

        results = await store.list_tools("t1")
        assert len(results) == 1
        r = results[0]
        assert r.handler_ref == "os.path:join"
        assert r.risk_tier == "medium"
        assert r.is_state_changing is True

    asyncio.run(run())


def test_tool_store_delete() -> None:
    store = SQLiteToolStore(":memory:")

    async def run() -> None:
        await store.save_tool("t1", _tool("my_tool", "t1"))
        await store.delete_tool("t1", "my_tool")
        results = await store.list_tools("t1")
        assert results == []

    asyncio.run(run())


def test_tool_store_delete_nonexistent_is_noop() -> None:
    store = SQLiteToolStore(":memory:")

    async def run() -> None:
        await store.delete_tool("t1", "does_not_exist")

    asyncio.run(run())


def test_tool_store_tenant_isolation() -> None:
    store = SQLiteToolStore(":memory:")

    async def run() -> None:
        await store.save_tool("t1", _tool("shared_name", "t1"))
        await store.save_tool("t2", _tool("shared_name", "t2"))

        t1_tools = await store.list_tools("t1")
        t2_tools = await store.list_tools("t2")
        assert len(t1_tools) == 1
        assert len(t2_tools) == 1
        assert t1_tools[0].tenant_id == "t1"
        assert t2_tools[0].tenant_id == "t2"

    asyncio.run(run())


def test_tool_store_list_tenant_ids() -> None:
    store = SQLiteToolStore(":memory:")

    async def run() -> None:
        await store.save_tool("alpha", _tool("a", "alpha"))
        await store.save_tool("beta", _tool("b", "beta"))
        ids = await store.list_tenant_ids()
        assert sorted(ids) == ["alpha", "beta"]

    asyncio.run(run())


def test_tool_store_record_fields_round_trip() -> None:
    store = SQLiteToolStore(":memory:")

    async def run() -> None:
        original = PersistedToolRecord(
            name="rich_tool",
            handler_ref="json:dumps",
            tenant_id="t1",
            risk_tier="high",
            is_state_changing=True,
            timeout_ms=12000,
            description="A rich tool",
            parameters_schema={"type": "object", "properties": {"x": {"type": "integer"}}},
            metadata={"handler_ref": "json:dumps", "extra": "value"},
        )
        await store.save_tool("t1", original)
        results = await store.list_tools("t1")
        assert len(results) == 1
        r = results[0]
        assert r.name == "rich_tool"
        assert r.handler_ref == "json:dumps"
        assert r.risk_tier == "high"
        assert r.is_state_changing is True
        assert r.timeout_ms == 12000
        assert r.description == "A rich tool"
        assert r.parameters_schema == {"type": "object", "properties": {"x": {"type": "integer"}}}
        assert r.metadata == {"handler_ref": "json:dumps", "extra": "value"}

    asyncio.run(run())


# ---------------------------------------------------------------------------
# SQLiteAgentStore
# ---------------------------------------------------------------------------


def test_agent_store_save_and_list() -> None:
    store = SQLiteAgentStore(":memory:")

    async def run() -> None:
        await store.save_agent("t1", _agent("a1", "t1"))
        await store.save_agent("t1", _agent("a2", "t1"))
        results = await store.list_agents("t1")
        ids = [r.agent_id for r in results]
        assert sorted(ids) == ["a1", "a2"]

    asyncio.run(run())


def test_agent_store_list_empty_tenant() -> None:
    store = SQLiteAgentStore(":memory:")

    async def run() -> None:
        results = await store.list_agents("empty")
        assert results == []

    asyncio.run(run())


def test_agent_store_upsert_overwrites() -> None:
    store = SQLiteAgentStore(":memory:")

    async def run() -> None:
        await store.save_agent("t1", _agent("a1", "t1"))

        updated = PersistedAgentRecord(
            agent_id="a1",
            role="reviewer",
            tenant_id="t1",
            capability_tags=["review", "retrieval"],
            instructions="Be critical",
            metadata={"model": "gpt-4o"},
        )
        await store.save_agent("t1", updated)

        results = await store.list_agents("t1")
        assert len(results) == 1
        r = results[0]
        assert r.role == "reviewer"
        assert sorted(r.capability_tags) == ["retrieval", "review"]
        assert r.instructions == "Be critical"

    asyncio.run(run())


def test_agent_store_delete() -> None:
    store = SQLiteAgentStore(":memory:")

    async def run() -> None:
        await store.save_agent("t1", _agent("a1", "t1"))
        await store.delete_agent("t1", "a1")
        results = await store.list_agents("t1")
        assert results == []

    asyncio.run(run())


def test_agent_store_delete_nonexistent_is_noop() -> None:
    store = SQLiteAgentStore(":memory:")

    async def run() -> None:
        await store.delete_agent("t1", "ghost")

    asyncio.run(run())


def test_agent_store_tenant_isolation() -> None:
    store = SQLiteAgentStore(":memory:")

    async def run() -> None:
        await store.save_agent("t1", _agent("shared-id", "t1"))
        await store.save_agent("t2", _agent("shared-id", "t2"))

        t1 = await store.list_agents("t1")
        t2 = await store.list_agents("t2")
        assert len(t1) == 1
        assert len(t2) == 1
        assert t1[0].tenant_id == "t1"
        assert t2[0].tenant_id == "t2"

    asyncio.run(run())


def test_agent_store_list_tenant_ids() -> None:
    store = SQLiteAgentStore(":memory:")

    async def run() -> None:
        await store.save_agent("alpha", _agent("a", "alpha"))
        await store.save_agent("beta", _agent("b", "beta"))
        ids = await store.list_tenant_ids()
        assert sorted(ids) == ["alpha", "beta"]

    asyncio.run(run())


def test_agent_store_record_fields_round_trip() -> None:
    store = SQLiteAgentStore(":memory:")

    async def run() -> None:
        original = PersistedAgentRecord(
            agent_id="rich-agent",
            role="orchestrator",
            tenant_id="t1",
            capability_tags=["tool_use", "workflow_routing"],
            instructions="Orchestrate tasks",
            metadata={"model": "gpt-4o", "priority": 1},
        )
        await store.save_agent("t1", original)
        results = await store.list_agents("t1")
        assert len(results) == 1
        r = results[0]
        assert r.agent_id == "rich-agent"
        assert r.role == "orchestrator"
        assert sorted(r.capability_tags) == ["tool_use", "workflow_routing"]
        assert r.instructions == "Orchestrate tasks"
        assert r.metadata == {"model": "gpt-4o", "priority": 1}

    asyncio.run(run())
