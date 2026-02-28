"""
File: audit_store.py
Path: src/persistence/audit_store.py
Role: In-memory append-only audit store implementation.
Used By:
 - src/persistence/factory.py
Depends On:
 - src/persistence/contracts.py
Notes:
 - Preserves append order for deterministic audit replay in tests.
"""

from __future__ import annotations

from src.persistence.contracts import AuditRecord, AuditStore


class InMemoryAuditStore(AuditStore):
    def __init__(self) -> None:
        self._records: list[AuditRecord] = []

    async def append_audit_event(self, record: AuditRecord) -> None:
        self._records.append(record)

    async def query_audit_events(self, correlation_id: str, tenant_id: str = "default") -> list[AuditRecord]:
        return [r for r in self._records if r.correlation_id == correlation_id and r.tenant_id == tenant_id]

