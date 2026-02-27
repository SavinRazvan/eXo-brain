"""
File: runtime_adapter.py
Path: src/runtime/runtime_adapter.py
Role: Provider-neutral runtime adapter contract for model backends.
Used By:
 - src/runtime/openai_agents_runtime.py
 - src/core/orchestrator.py
Depends On:
 - src/schemas/events.py
 - src/schemas/tool_io.py
 - src/runtime/capability_map.py
Notes:
 - Core orchestration must only depend on this interface, never provider SDKs.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator, Any

from src.runtime.capability_map import HealthStatus, ProviderCapabilityMap
from src.schemas.events import RuntimeEvent
from src.schemas.tool_io import ToolResult


@dataclass(slots=True)
class SessionHandle:
    session_id: str
    provider_id: str
    metadata: dict[str, Any]


class RuntimeAdapter(ABC):
    @abstractmethod
    async def start_session(
        self,
        session_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> SessionHandle:
        raise NotImplementedError

    @abstractmethod
    async def run_turn(
        self,
        session_id: str,
        user_input: str,
        context: dict[str, Any],
    ) -> AsyncIterator[RuntimeEvent]:
        raise NotImplementedError

    @abstractmethod
    async def submit_tool_results(
        self,
        session_id: str,
        run_id: str,
        tool_results: list[ToolResult],
    ) -> AsyncIterator[RuntimeEvent]:
        raise NotImplementedError

    @abstractmethod
    def get_capabilities(self) -> ProviderCapabilityMap:
        raise NotImplementedError

    @abstractmethod
    async def healthcheck(self) -> HealthStatus:
        raise NotImplementedError
