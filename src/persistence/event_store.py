"""
File: event_store.py
Path: src/persistence/event_store.py
Role: In-memory runtime event store implementation.
Used By:
 - src/persistence/factory.py
Depends On:
 - src/persistence/contracts.py
Notes:
 - Keeps tenant-aware query support for isolation checks.
"""

from __future__ import annotations

from src.persistence.contracts import EventRecord, EventStore


class InMemoryEventStore(EventStore):
    def __init__(self) -> None:
        self._records: list[EventRecord] = []

    async def append_event(self, record: EventRecord) -> None:
        self._records.append(record)

    async def query_events(self, correlation_id: str, tenant_id: str = "default") -> list[EventRecord]:
        return [r for r in self._records if r.correlation_id == correlation_id and r.tenant_id == tenant_id]

