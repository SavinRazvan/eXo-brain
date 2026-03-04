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

    async def list_audit_events(self, tenant_id: str = "default", limit: int = 100) -> list[AuditRecord]:
        bounded = max(1, min(int(limit), 1000))
        tenant_records = [record for record in self._records if record.tenant_id == tenant_id]
        return tenant_records[-bounded:]

    async def cleanup_audit_events(self, tenant_id: str = "default", max_records: int = 1000) -> int:
        bounded = max(int(max_records), 0)
        tenant_indexes = [idx for idx, record in enumerate(self._records) if record.tenant_id == tenant_id]
        overflow = max(0, len(tenant_indexes) - bounded)
        if overflow <= 0:
            return 0
        indexes_to_remove = set(tenant_indexes[:overflow])
        self._records = [record for idx, record in enumerate(self._records) if idx not in indexes_to_remove]
        return overflow

