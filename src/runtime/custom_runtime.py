"""
File: custom_runtime.py
Path: src/runtime/custom_runtime.py
Role: Custom/runtime-agnostic adapter implementation for local or bespoke providers.
Used By:
 - tests/modules/runtime/test_runtime_adapter_contract.py
 - tests/modules/core/test_multi_adapter_workflow_parity.py
Depends On:
 - src/runtime/runtime_adapter.py
 - src/runtime/capability_map.py
 - src/schemas/events.py
 - src/schemas/tool_io.py
Notes:
 - Serves as baseline adapter template for providers outside OpenAI-compatible APIs.
"""

from __future__ import annotations

import uuid
from typing import Any, AsyncIterator

from src.runtime.capability_map import HealthState, HealthStatus, ProviderCapabilityMap, SecurityTier
from src.runtime.runtime_adapter import RuntimeAdapter, SessionHandle
from src.schemas.events import RuntimeEvent
from src.schemas.tool_io import ToolResult


class CustomRuntimeAdapter(RuntimeAdapter):
    def __init__(self, provider_id: str = "custom") -> None:
        self._provider_id = provider_id
        self._sessions: set[str] = set()

    async def start_session(
        self,
        session_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> SessionHandle:
        self._sessions.add(session_id)
        return SessionHandle(session_id=session_id, provider_id=self._provider_id, metadata=metadata or {})

    async def run_turn(
        self,
        session_id: str,
        user_input: str,
        context: dict[str, Any],
    ) -> AsyncIterator[RuntimeEvent]:
        context = context if isinstance(context, dict) else {}
        run_id = str(context.get("run_id", f"run_{uuid.uuid4().hex[:8]}"))
        try:
            if not isinstance(user_input, str):
                raise ValueError("user_input must be a string")
            yield RuntimeEvent.output_delta(
                session_id=session_id,
                run_id=run_id,
                text=f"custom-adapter-echo: {user_input}",
                correlation_id=run_id,
            )
            yield RuntimeEvent.run_complete(
                session_id=session_id,
                run_id=run_id,
                output={"status": "completed", "provider_id": self._provider_id},
                correlation_id=run_id,
            )
        except Exception as exc:  # pragma: no cover - defensive adapter boundary
            yield RuntimeEvent.error(
                session_id=session_id,
                run_id=run_id,
                code="RUNTIME_TURN_ERROR",
                message=str(exc),
                correlation_id=run_id,
            )

    async def submit_tool_results(
        self,
        session_id: str,
        run_id: str,
        tool_results: list[ToolResult],
    ) -> AsyncIterator[RuntimeEvent]:
        try:
            if not isinstance(tool_results, list):
                raise ValueError("tool_results must be a list")
            yield RuntimeEvent.run_complete(
                session_id=session_id,
                run_id=run_id,
                output={
                    "status": "completed",
                    "tool_results_count": len(tool_results),
                    "provider_id": self._provider_id,
                },
                correlation_id=run_id,
            )
        except Exception as exc:  # pragma: no cover
            yield RuntimeEvent.error(
                session_id=session_id,
                run_id=run_id,
                code="RUNTIME_TOOL_RESULT_ERROR",
                message=str(exc),
                correlation_id=run_id,
            )

    def get_capabilities(self) -> ProviderCapabilityMap:
        return ProviderCapabilityMap(
            provider_id=self._provider_id,
            supports_agents_sdk_native=False,
            supports_openai_compatible_api=False,
            supports_streaming=True,
            supports_function_calling=True,
            supports_structured_output=True,
            supports_handoffs=False,
            reliability_score=4,
            security_tier=SecurityTier.LOCAL_ONLY,
            recommended_runtime_mode="deterministic",
        )

    async def healthcheck(self) -> HealthStatus:
        return HealthStatus(state=HealthState.HEALTHY, reason="adapter-initialized")
