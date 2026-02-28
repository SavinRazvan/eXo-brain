"""
File: host_adapter.py
Path: src/integration/host_adapter.py
Role: Transport-agnostic integration boundary that feeds requests into orchestration core.
Used By:
 - API/CLI host layers (future)
Depends On:
 - src/core/orchestrator.py
 - src/core/session_context.py
 - src/schemas/events.py
Notes:
 - Keep this boundary thin; no policy/runtime ownership in integration layer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from src.core.orchestrator import Orchestrator
from src.core.session_context import SessionContext
from src.schemas.events import RuntimeEvent


class HostAdapter(ABC):
    @abstractmethod
    async def submit_turn(self, session: SessionContext, user_input: str) -> AsyncIterator[RuntimeEvent]:
        """
        Submit one user turn to the orchestration core and stream runtime events.
        """


class OrchestratorHostAdapter(HostAdapter):
    def __init__(self, orchestrator: Orchestrator) -> None:
        self._orchestrator = orchestrator

    async def submit_turn(self, session: SessionContext, user_input: str) -> AsyncIterator[RuntimeEvent]:
        context = {
            "run_id": session.run_id,
            "job_id": session.job_id,
            "task_id": session.task_id,
            "agent_id": session.agent_id,
            "provider_id": session.provider_id,
            "correlation_id": session.correlation_id,
            "session_metadata": session.metadata,
            "identity": {
                "subject": session.identity.subject,
                "actor_type": session.identity.actor_type.value,
                "roles": list(session.identity.roles),
                "tenant_id": session.identity.tenant_id,
                "token_id": session.identity.token_id,
            }
            if session.identity
            else None,
        }
        async for event in self._orchestrator.run_turn(session.session_id, user_input, context):
            yield event
