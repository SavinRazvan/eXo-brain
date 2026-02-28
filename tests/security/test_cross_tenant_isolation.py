"""
File: test_cross_tenant_isolation.py
Path: tests/security/test_cross_tenant_isolation.py
Role: Security tests for tenant overlay and event isolation behavior.
Used By:
 - pytest
Depends On:
 - src/tenancy/policy_overlay.py
 - src/persistence/event_store.py
 - src/persistence/contracts.py
Notes:
 - Verifies tenant-scoped queries do not leak cross-tenant records.
"""

import asyncio

from src.persistence.contracts import EventRecord
from src.persistence.event_store import InMemoryEventStore
from src.tenancy.policy_overlay import TenantPolicyOverlayStore


def test_tenant_overlay_and_event_queries_are_isolated() -> None:
    overlays = TenantPolicyOverlayStore()
    overlays.set_overlay("tenant_a", {"risk_mode": "strict"})
    overlays.set_overlay("tenant_b", {"risk_mode": "relaxed"})
    assert overlays.get_overlay("tenant_a") == {"risk_mode": "strict"}
    assert overlays.get_overlay("tenant_b") == {"risk_mode": "relaxed"}

    async def scenario() -> None:
        store = InMemoryEventStore()
        await store.append_event(EventRecord(event_id="e1", correlation_id="job_1", tenant_id="tenant_a"))
        await store.append_event(EventRecord(event_id="e2", correlation_id="job_1", tenant_id="tenant_b"))
        tenant_a_events = await store.query_events("job_1", tenant_id="tenant_a")
        tenant_b_events = await store.query_events("job_1", tenant_id="tenant_b")
        assert [e.event_id for e in tenant_a_events] == ["e1"]
        assert [e.event_id for e in tenant_b_events] == ["e2"]

    asyncio.run(scenario())

