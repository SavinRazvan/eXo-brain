"""
File: test_sqlite_audit_store.py
Path: tests/modules/audit/test_sqlite_audit_store.py
Role: Unit tests for the durable SQLite audit store.
Used By:
 - pytest
Depends On:
 - src/persistence/adapters/sqlite_audit.py
 - src/persistence/contracts.py
Notes:
 - Confirms audit events survive store re-instantiation and cleanup remains tenant-scoped.
"""

from __future__ import annotations

import pytest

from src.modules.audit_observability.service import AuditObservabilityError
from src.persistence.adapters.sqlite_audit import SQLiteAuditStore
from src.persistence.contracts import AuditRecord


@pytest.mark.asyncio
async def test_sqlite_audit_store_persists_events_across_instances(tmp_path) -> None:
    db_path = tmp_path / "audit.db"
    store = SQLiteAuditStore(db_path)
    await store.append_audit_event(
        AuditRecord(
            event_id="evt-1",
            correlation_id="corr-1",
            tenant_id="tenant-a",
            event_type="tool_call",
            payload={"step": 1},
        )
    )
    await store.append_audit_event(
        AuditRecord(
            event_id="evt-2",
            correlation_id="corr-1",
            tenant_id="tenant-a",
            event_type="tool_result",
            payload={"step": 2},
        )
    )

    reopened = SQLiteAuditStore(db_path)
    records = await reopened.query_audit_events(correlation_id="corr-1", tenant_id="tenant-a")

    assert [record.event_id for record in records] == ["evt-1", "evt-2"]
    assert records[0].payload == {"step": 1}
    assert records[1].payload == {"step": 2}


@pytest.mark.asyncio
async def test_sqlite_audit_store_cleanup_prunes_oldest_records(tmp_path) -> None:
    db_path = tmp_path / "audit_cleanup.db"
    store = SQLiteAuditStore(db_path)
    for index in range(3):
        await store.append_audit_event(
            AuditRecord(
                event_id=f"evt-{index}",
                correlation_id=f"corr-{index}",
                tenant_id="tenant-a",
                event_type="audit",
                payload={"index": index},
            )
        )

    pruned = await store.cleanup_audit_events(tenant_id="tenant-a", max_records=1)
    remaining = await store.list_audit_events(tenant_id="tenant-a", limit=10)

    assert pruned == 2
    assert [record.event_id for record in remaining] == ["evt-2"]


def test_audit_observability_error_str_returns_detail() -> None:
    assert str(AuditObservabilityError(status_code=503, detail="audit-missing")) == "audit-missing"


@pytest.mark.asyncio
async def test_sqlite_audit_store_memory_backend_reuses_shared_connection_and_noop_cleanup() -> None:
    store = SQLiteAuditStore(":memory:")
    await store.append_audit_event(
        AuditRecord(
            event_id="evt-memory",
            correlation_id="corr-memory",
            tenant_id="tenant-a",
            event_type="audit",
            payload={"ok": True},
        )
    )

    assert store._connect() is store._shared_conn
    assert await store.cleanup_audit_events(tenant_id="tenant-a", max_records=5) == 0
