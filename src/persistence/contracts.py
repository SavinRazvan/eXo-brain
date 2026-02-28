"""
File: contracts.py
Path: src/persistence/contracts.py
Role: Persistence contracts for session state and runtime checkpoints.
Used By:
 - src/core/checkpoint_store.py
 - src/core/background_runtime.py
Depends On:
 - src/core/session_context.py
 - src/schemas/tool_io.py
Notes:
 - Implementations should remain adapter-based (sqlite/postgres/etc.).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.core.session_context import SessionContext


class CheckpointStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class SessionRecord:
    session: SessionContext
    tenant_id: str = "default"
    state: str = "active"
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CheckpointRecord:
    job_id: str
    node_id: str
    status: CheckpointStatus
    tenant_id: str = "default"
    attempt: int = 1
    reason_code: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


class SessionStore(ABC):
    @abstractmethod
    async def save_session(self, record: SessionRecord) -> None:
        """Persist session context and mutable state."""

    @abstractmethod
    async def get_session(self, session_id: str) -> SessionRecord | None:
        """Load a previously stored session record."""


class CheckpointStoreContract(ABC):
    @abstractmethod
    async def save_checkpoint(self, checkpoint: CheckpointRecord) -> None:
        """Persist checkpoint state for a given job/node."""

    @abstractmethod
    async def list_checkpoints(self, job_id: str) -> list[CheckpointRecord]:
        """List checkpoints associated with a job."""

    @abstractmethod
    async def get_checkpoint(self, job_id: str, node_id: str) -> CheckpointRecord | None:
        """Fetch a single checkpoint by composite key."""


@dataclass(slots=True)
class WorkflowRecord:
    workflow_id: str
    version: str
    tenant_id: str = "default"
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AuditRecord:
    event_id: str
    correlation_id: str
    tenant_id: str = "default"
    event_type: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EventRecord:
    event_id: str
    correlation_id: str
    tenant_id: str = "default"
    payload: dict[str, Any] = field(default_factory=dict)


class WorkflowStore(ABC):
    @abstractmethod
    async def save_workflow(self, record: WorkflowRecord) -> None:
        """Persist one workflow version."""

    @abstractmethod
    async def load_workflow(self, workflow_id: str, version: str, tenant_id: str = "default") -> WorkflowRecord | None:
        """Load a workflow record for one tenant."""


class AuditStore(ABC):
    @abstractmethod
    async def append_audit_event(self, record: AuditRecord) -> None:
        """Append one audit event."""

    @abstractmethod
    async def query_audit_events(self, correlation_id: str, tenant_id: str = "default") -> list[AuditRecord]:
        """Query audit records by correlation."""


class EventStore(ABC):
    @abstractmethod
    async def append_event(self, record: EventRecord) -> None:
        """Append one runtime event."""

    @abstractmethod
    async def query_events(self, correlation_id: str, tenant_id: str = "default") -> list[EventRecord]:
        """Query runtime events by correlation."""
