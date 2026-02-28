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
    state: str = "active"
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CheckpointRecord:
    job_id: str
    node_id: str
    status: CheckpointStatus
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
