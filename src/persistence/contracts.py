"""
File: contracts.py
Path: src/persistence/contracts.py
Role: Persistence contracts for session state, checkpoints, tools, agents, and API keys.
Used By:
 - src/core/checkpoint_store.py
 - src/core/background_runtime.py
 - src/api/startup.py
 - src/api/routers/tools.py
 - src/api/routers/agents.py
 - src/api/routers/admin_keys.py
 - src/api/middleware/auth.py
Depends On:
 - src/core/session_context.py
Notes:
 - Implementations should remain adapter-based (sqlite/postgres/etc.).
 - PersistedToolRecord and PersistedAgentRecord are serializable — no callables or enums.
 - ApiKeyRecord stores a SHA-256 hash of the actual key — never the plaintext key.
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


@dataclass(slots=True)
class PersistenceIsolationError(Exception):
    reason_code: str
    message: str
    tenant_id: str
    requested_tenant_id: str

    def __str__(self) -> str:
        return f"{self.reason_code}: {self.message}"


class SessionStore(ABC):
    @abstractmethod
    async def save_session(self, record: SessionRecord) -> None:
        """Persist session context and mutable state."""

    @abstractmethod
    async def get_session(self, session_id: str, tenant_id: str = "default") -> SessionRecord | None:
        """Load a previously stored session record."""


class CheckpointStoreContract(ABC):
    @abstractmethod
    async def save_checkpoint(self, checkpoint: CheckpointRecord) -> None:
        """Persist checkpoint state for a given job/node."""

    @abstractmethod
    async def list_checkpoints(self, job_id: str, tenant_id: str = "default") -> list[CheckpointRecord]:
        """List checkpoints associated with a job."""

    @abstractmethod
    async def get_checkpoint(self, job_id: str, node_id: str, tenant_id: str = "default") -> CheckpointRecord | None:
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


# ---------------------------------------------------------------------------
# Tool and Agent persistence records (serializable — no callables or enums)
# ---------------------------------------------------------------------------


@dataclass
class PersistedToolRecord:
    """Serializable snapshot of a ToolDescriptor for durable storage.

    handler_ref uses 'module.path:function_name' format and is re-resolved on hydration.
    """

    name: str
    handler_ref: str
    tenant_id: str = "default"
    risk_tier: str = "low"
    is_state_changing: bool = False
    timeout_ms: int = 30000
    description: str = ""
    parameters_schema: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PersistedAgentRecord:
    """Serializable snapshot of an AgentSpec for durable storage."""

    agent_id: str
    role: str
    tenant_id: str = "default"
    capability_tags: list[str] = field(default_factory=list)
    instructions: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class ToolStore(ABC):
    @abstractmethod
    async def save_tool(self, tenant_id: str, record: PersistedToolRecord) -> None:
        """Upsert a tool record for the given tenant."""

    @abstractmethod
    async def delete_tool(self, tenant_id: str, tool_name: str) -> None:
        """Remove a tool record for the given tenant."""

    @abstractmethod
    async def list_tools(self, tenant_id: str) -> list[PersistedToolRecord]:
        """List all persisted tool records for a tenant."""

    @abstractmethod
    async def list_tenant_ids(self) -> list[str]:
        """Return all tenant IDs that have at least one persisted tool."""


class AgentStore(ABC):
    @abstractmethod
    async def save_agent(self, tenant_id: str, record: PersistedAgentRecord) -> None:
        """Upsert an agent record for the given tenant."""

    @abstractmethod
    async def delete_agent(self, tenant_id: str, agent_id: str) -> None:
        """Remove an agent record for the given tenant."""

    @abstractmethod
    async def list_agents(self, tenant_id: str) -> list[PersistedAgentRecord]:
        """List all persisted agent records for a tenant."""

    @abstractmethod
    async def list_tenant_ids(self) -> list[str]:
        """Return all tenant IDs that have at least one persisted agent."""


# ---------------------------------------------------------------------------
# API key persistence
# ---------------------------------------------------------------------------


@dataclass
class ApiKeyRecord:
    """Persisted API key entry.

    key_hash is a SHA-256 hex digest of the actual key — plaintext is never stored.
    roles is stored as a comma-separated string at the store level; use list[str] here.
    """

    key_id: str
    tenant_id: str
    subject: str
    key_hash: str
    roles: list[str] = field(default_factory=list)
    description: str = ""
    enabled: bool = True
    created_at: str = ""


class ApiKeyStore(ABC):
    @abstractmethod
    async def save_key(self, record: ApiKeyRecord) -> None:
        """Insert or replace an API key record."""

    @abstractmethod
    async def get_key(self, key_id: str) -> ApiKeyRecord | None:
        """Return a key record by key_id, or None if not found."""

    @abstractmethod
    async def lookup_by_hash(self, key_hash: str) -> ApiKeyRecord | None:
        """Return the key record matching the given SHA-256 hash, or None."""

    @abstractmethod
    async def delete_key(self, key_id: str) -> None:
        """Remove a key record by key_id."""

    @abstractmethod
    async def list_keys(self, tenant_id: str | None = None) -> list[ApiKeyRecord]:
        """List all key records, optionally filtered by tenant_id."""
