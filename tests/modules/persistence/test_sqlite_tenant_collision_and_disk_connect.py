"""
File: test_sqlite_tenant_collision_and_disk_connect.py
Path: tests/modules/persistence/test_sqlite_tenant_collision_and_disk_connect.py
Role: Covers SQLite session/checkpoint tenant collision paths and on-disk store connections.
Used By:
 - pytest
Depends On:
 - src/persistence/adapters/sqlite.py
 - src/persistence/contracts.py
Notes:
 - Exercises branches guarded by _assert_tenant_match and non-memory ApiKey/Provider _connect.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.core.session_context import SessionContext
from src.persistence.adapters.sqlite import SQLiteApiKeyStore, SQLiteCheckpointStore, SQLiteProviderStore, SQLiteSessionStore
from src.persistence.contracts import (
    ApiKeyRecord,
    CheckpointRecord,
    CheckpointStatus,
    PersistenceIsolationError,
    PersistedProviderRecord,
    SessionRecord,
)


@pytest.mark.asyncio
async def test_sqlite_get_session_raises_when_session_id_collides_across_tenants(tmp_path: Path) -> None:
    store = SQLiteSessionStore(tmp_path / "sessions.db")
    session = SessionContext(
        session_id="sess-shared",
        run_id="r1",
        job_id="j1",
        task_id="t1",
        agent_id="a1",
        provider_id="p1",
        correlation_id="c1",
    )
    await store.save_session(SessionRecord(session=session, tenant_id="tenant-a", state="active", data={}))
    with pytest.raises(PersistenceIsolationError, match="PERSISTENCE_TENANT_ISOLATION"):
        await store.get_session("sess-shared", tenant_id="tenant-b")


@pytest.mark.asyncio
async def test_sqlite_get_checkpoint_raises_when_job_node_collides_across_tenants(tmp_path: Path) -> None:
    store = SQLiteCheckpointStore(tmp_path / "checkpoints.db")
    await store.save_checkpoint(
        CheckpointRecord(
            tenant_id="tenant-a",
            job_id="job-shared",
            node_id="n1",
            status=CheckpointStatus.COMPLETED,
            attempt=1,
            payload={"ok": True},
        )
    )
    with pytest.raises(PersistenceIsolationError, match="PERSISTENCE_TENANT_ISOLATION"):
        await store.get_checkpoint("job-shared", "n1", tenant_id="tenant-b")


@pytest.mark.asyncio
async def test_sqlite_api_key_store_file_path_uses_disk_connection(tmp_path: Path) -> None:
    store = SQLiteApiKeyStore(tmp_path / "keys.db")
    record = ApiKeyRecord(
        key_id="k1",
        tenant_id="t1",
        subject="u1",
        key_hash="abc",
        roles=["admin"],
    )
    await store.save_key(record)
    loaded = await store.get_key("k1")
    assert loaded is not None
    assert loaded.subject == "u1"
    assert [record.key_id for record in await store.list_keys()] == ["k1"]


@pytest.mark.asyncio
async def test_sqlite_provider_store_file_path_uses_disk_connection(tmp_path: Path) -> None:
    store = SQLiteProviderStore(tmp_path / "providers.db")
    record = PersistedProviderRecord(
        provider_id="p-disk",
        display_name="Disk Provider",
        adapter_class="OpenAIAgentsRuntimeAdapter",
        enabled=True,
        profile="managed_vendor",
        priority=1,
        endpoint_base_url="https://example.com",
        endpoint_api_type="openai_native",
        auth_type="api_key",
        auth_api_key_env_var="KEY",
        model="gpt-4o-mini",
    )
    await store.save_provider(record)
    loaded = await store.get_provider("p-disk")
    assert loaded is not None
    assert loaded.display_name == "Disk Provider"


@pytest.mark.asyncio
async def test_sqlite_api_key_store_memory_reuses_shared_connection() -> None:
    """Covers SQLiteApiKeyStore._connect fast path for :memory: (returns shared handle)."""
    store = SQLiteApiKeyStore(":memory:")
    record = ApiKeyRecord(
        key_id="mem-k1",
        tenant_id="t1",
        subject="u1",
        key_hash="hash-mem-1",
        roles=["admin"],
    )
    await store.save_key(record)
    loaded = await store.lookup_by_hash("hash-mem-1")
    assert loaded is not None
    assert loaded.key_id == "mem-k1"


@pytest.mark.asyncio
async def test_sqlite_provider_store_memory_reuses_shared_connection() -> None:
    """Covers SQLiteProviderStore._connect fast path for :memory: (returns shared handle)."""
    store = SQLiteProviderStore(":memory:")
    record = PersistedProviderRecord(
        provider_id="p-mem",
        display_name="Mem Provider",
        adapter_class="OpenAIAgentsRuntimeAdapter",
        enabled=True,
        profile="managed_vendor",
        priority=1,
        endpoint_base_url="https://example.com",
        endpoint_api_type="openai_native",
        auth_type="api_key",
        auth_api_key_env_var="KEY",
        model="gpt-4o-mini",
    )
    await store.save_provider(record)
    loaded = await store.get_provider("p-mem")
    assert loaded is not None
    assert loaded.provider_id == "p-mem"


@pytest.mark.asyncio
async def test_sqlite_get_session_returns_none_when_missing_without_collision(tmp_path: Path) -> None:
    store = SQLiteSessionStore(tmp_path / "sessions_missing.db")
    assert await store.get_session("no-such-session", tenant_id="tenant-x") is None


@pytest.mark.asyncio
async def test_sqlite_get_checkpoint_returns_none_when_missing_without_collision(tmp_path: Path) -> None:
    store = SQLiteCheckpointStore(tmp_path / "cp_missing.db")
    assert await store.get_checkpoint("job-x", "node-y", tenant_id="tenant-x") is None
