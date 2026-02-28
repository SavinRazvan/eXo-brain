"""
File: session_store.py
Path: src/core/session_store.py
Role: In-memory session persistence implementation for orchestration session lifecycle.
Used By:
 - src/integration/host_adapter.py
 - tests/unit/test_session_store.py
Depends On:
 - src/persistence/contracts.py
Notes:
 - This implementation is a local default; durable adapters can replace it.
"""

from __future__ import annotations

from dataclasses import replace

from src.persistence.contracts import SessionRecord, SessionStore


class InMemorySessionStore(SessionStore):
    def __init__(self) -> None:
        self._records: dict[str, SessionRecord] = {}

    async def save_session(self, record: SessionRecord) -> None:
        self._records[record.session.session_id] = replace(
            record,
            session=replace(record.session, metadata=dict(record.session.metadata)),
            data=dict(record.data),
        )

    async def get_session(self, session_id: str) -> SessionRecord | None:
        record = self._records.get(session_id)
        if record is None:
            return None
        return replace(
            record,
            session=replace(record.session, metadata=dict(record.session.metadata)),
            data=dict(record.data),
        )
