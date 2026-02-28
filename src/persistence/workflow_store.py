"""
File: workflow_store.py
Path: src/persistence/workflow_store.py
Role: In-memory workflow store implementation over workflow contracts.
Used By:
 - src/persistence/factory.py
Depends On:
 - src/persistence/contracts.py
Notes:
 - Adapter-backed implementations can replace this store without core changes.
"""

from __future__ import annotations

from src.persistence.contracts import WorkflowRecord, WorkflowStore


class InMemoryWorkflowStore(WorkflowStore):
    def __init__(self) -> None:
        self._records: dict[tuple[str, str, str], WorkflowRecord] = {}

    async def save_workflow(self, record: WorkflowRecord) -> None:
        self._records[(record.tenant_id, record.workflow_id, record.version)] = record

    async def load_workflow(self, workflow_id: str, version: str, tenant_id: str = "default") -> WorkflowRecord | None:
        return self._records.get((tenant_id, workflow_id, version))

