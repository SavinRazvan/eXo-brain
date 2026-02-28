"""
File: test_persistence_store_contracts.py
Path: tests/integration/test_persistence_store_contracts.py
Role: Integration contract tests for new workflow/audit/event stores.
Used By:
 - pytest
Depends On:
 - src/persistence/factory.py
 - src/persistence/contracts.py
Notes:
 - Ensures new stores support basic save/query semantics.
"""

import asyncio

from src.persistence.contracts import AuditRecord, EventRecord, WorkflowRecord
from src.persistence.factory import build_default_persistence_bundle


def test_persistence_bundle_stores_roundtrip_records() -> None:
    bundle = build_default_persistence_bundle()

    async def scenario() -> None:
        await bundle.workflow_store.save_workflow(
            WorkflowRecord(workflow_id="wf_1", version="1.0", tenant_id="tenant_a", payload={"step": 1})
        )
        loaded = await bundle.workflow_store.load_workflow("wf_1", "1.0", tenant_id="tenant_a")
        assert loaded is not None and loaded.payload == {"step": 1}

        await bundle.audit_store.append_audit_event(
            AuditRecord(event_id="a1", correlation_id="corr_1", tenant_id="tenant_a", event_type="policy")
        )
        audits = await bundle.audit_store.query_audit_events("corr_1", tenant_id="tenant_a")
        assert [item.event_id for item in audits] == ["a1"]

        await bundle.event_store.append_event(EventRecord(event_id="e1", correlation_id="corr_1", tenant_id="tenant_a"))
        events = await bundle.event_store.query_events("corr_1", tenant_id="tenant_a")
        assert [item.event_id for item in events] == ["e1"]

    asyncio.run(scenario())

