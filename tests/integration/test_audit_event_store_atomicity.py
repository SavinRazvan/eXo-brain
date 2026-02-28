"""
File: test_audit_event_store_atomicity.py
Path: tests/integration/test_audit_event_store_atomicity.py
Role: Atomicity-oriented integration checks for in-memory audit/event appends.
Used By:
 - pytest
Depends On:
 - src/persistence/factory.py
 - src/persistence/contracts.py
Notes:
 - Validates append order and presence across rapid sequential writes.
"""

import asyncio

from src.persistence.contracts import AuditRecord, EventRecord
from src.persistence.factory import build_default_persistence_bundle


def test_audit_and_event_append_order_is_deterministic() -> None:
    bundle = build_default_persistence_bundle()

    async def scenario() -> None:
        for index in range(5):
            await bundle.audit_store.append_audit_event(
                AuditRecord(event_id=f"a{index}", correlation_id="corr_atomic", tenant_id="tenant_a")
            )
            await bundle.event_store.append_event(
                EventRecord(event_id=f"e{index}", correlation_id="corr_atomic", tenant_id="tenant_a")
            )
        audits = await bundle.audit_store.query_audit_events("corr_atomic", tenant_id="tenant_a")
        events = await bundle.event_store.query_events("corr_atomic", tenant_id="tenant_a")
        assert [item.event_id for item in audits] == [f"a{i}" for i in range(5)]
        assert [item.event_id for item in events] == [f"e{i}" for i in range(5)]

    asyncio.run(scenario())

