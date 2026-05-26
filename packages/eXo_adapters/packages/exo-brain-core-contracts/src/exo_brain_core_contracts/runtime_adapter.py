"""
File: runtime_adapter.py
Path: packages/exo-brain-core-contracts/src/exo_brain_core_contracts/runtime_adapter.py
Role: Frozen provider-neutral runtime adapter contract.
Used By:
 - provider adapter packages
 - control plane orchestrator integration
Depends On:
 - packages/exo-brain-core-contracts/src/exo_brain_core_contracts/capability_map.py
 - packages/exo-brain-core-contracts/src/exo_brain_core_contracts/events.py
 - packages/exo-brain-core-contracts/src/exo_brain_core_contracts/tool_io.py
Notes:
 - Keep signatures stable for v1 compatibility.
 - `run_turn` / `submit_tool_results` are abstract as plain `def -> AsyncIterator` so type
   checkers see an async iterator from the call expression (implementations use `async def` + `yield`).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from exo_brain_core_contracts.capability_map import HealthStatus, ProviderCapabilityMap
from exo_brain_core_contracts.events import RuntimeEvent
from exo_brain_core_contracts.tool_io import ToolResult


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
    def run_turn(
        self,
        session_id: str,
        user_input: str,
        context: dict[str, Any],
    ) -> AsyncIterator[RuntimeEvent]:
        raise NotImplementedError

    @abstractmethod
    def submit_tool_results(
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
