"""
File: factory.py
Path: src/persistence/factory.py
Role: Persistence factory wiring default in-memory stores for runtime usage.
Used By:
 - bootstrap/runtime wiring (future)
Depends On:
 - src/persistence/audit_store.py
 - src/persistence/event_store.py
 - src/persistence/workflow_store.py
Notes:
 - Keeps store selection centralized and profile-driven.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.persistence.audit_store import InMemoryAuditStore
from src.persistence.event_store import InMemoryEventStore
from src.persistence.workflow_store import InMemoryWorkflowStore


@dataclass(slots=True)
class PersistenceBundle:
    workflow_store: InMemoryWorkflowStore
    audit_store: InMemoryAuditStore
    event_store: InMemoryEventStore


def build_default_persistence_bundle() -> PersistenceBundle:
    return PersistenceBundle(
        workflow_store=InMemoryWorkflowStore(),
        audit_store=InMemoryAuditStore(),
        event_store=InMemoryEventStore(),
    )

