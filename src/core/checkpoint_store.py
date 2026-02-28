"""
File: checkpoint_store.py
Path: src/core/checkpoint_store.py
Role: In-memory checkpoint store implementing persistence contracts for job replay/resume.
Used By:
 - src/core/scheduler.py
 - src/core/background_runtime.py
Depends On:
 - src/persistence/contracts.py
Notes:
 - This is the default local implementation; persistent adapters can replace it.
"""

from __future__ import annotations

from src.persistence.contracts import CheckpointRecord, CheckpointStoreContract


class InMemoryCheckpointStore(CheckpointStoreContract):
    def __init__(self) -> None:
        self._records: dict[str, dict[str, CheckpointRecord]] = {}

    async def save_checkpoint(self, checkpoint: CheckpointRecord) -> None:
        job_records = self._records.setdefault(checkpoint.job_id, {})
        job_records[checkpoint.node_id] = checkpoint

    async def list_checkpoints(self, job_id: str) -> list[CheckpointRecord]:
        return list(self._records.get(job_id, {}).values())

    async def get_checkpoint(self, job_id: str, node_id: str) -> CheckpointRecord | None:
        return self._records.get(job_id, {}).get(node_id)
