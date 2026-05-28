"""
File: runtime.py
Path: packages/exo-adapter-echo/src/exo_adapter_echo/runtime.py
Role: Minimal echo RuntimeAdapter for portability and conformance testing.
Used By:
 - exo_adapter_echo package consumers
Depends On:
 - exo_brain_core_contracts
Notes:
 - Mirrors behavior of the in-repo OpenAI-compatible echo adapter without transport/SDK calls.
"""

from __future__ import annotations

import uuid
from typing import Any, AsyncIterator

from exo_brain_core_contracts import (
    HealthState,
    HealthStatus,
    ProviderCapabilityMap,
    RuntimeAdapter,
    RuntimeEvent,
    RuntimeEventType,
    SecurityTier,
    SessionHandle,
    ToolResult,
)


class EchoRuntimeAdapter(RuntimeAdapter):
    """Deterministic echo adapter with no external calls."""

    def __init__(self, provider_id: str = "echo") -> None:
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
            yield RuntimeEvent(
                event_type=RuntimeEventType.OUTPUT_DELTA,
                session_id=session_id,
                run_id=run_id,
                correlation_id=run_id,
                payload={"text": f"echo:{user_input}"},
            )
            yield RuntimeEvent(
                event_type=RuntimeEventType.RUN_COMPLETE,
                session_id=session_id,
                run_id=run_id,
                correlation_id=run_id,
                payload={"status": "completed", "provider_id": self._provider_id},
            )
        except Exception as exc:
            yield RuntimeEvent(
                event_type=RuntimeEventType.ERROR,
                session_id=session_id,
                run_id=run_id,
                correlation_id=run_id,
                payload={"code": "RUNTIME_TURN_ERROR", "message": str(exc)},
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
            yield RuntimeEvent(
                event_type=RuntimeEventType.RUN_COMPLETE,
                session_id=session_id,
                run_id=run_id,
                correlation_id=run_id,
                payload={
                    "status": "completed",
                    "tool_results_count": len(tool_results),
                    "provider_id": self._provider_id,
                },
            )
        except Exception as exc:
            yield RuntimeEvent(
                event_type=RuntimeEventType.ERROR,
                session_id=session_id,
                run_id=run_id,
                correlation_id=run_id,
                payload={"code": "RUNTIME_TOOL_RESULT_ERROR", "message": str(exc)},
            )

    def get_capabilities(self) -> ProviderCapabilityMap:
        return ProviderCapabilityMap(
            provider_id=self._provider_id,
            supports_agents_sdk_native=False,
            supports_openai_compatible_api=True,
            supports_streaming=True,
            supports_function_calling=True,
            supports_structured_output=False,
            supports_handoffs=False,
            reliability_score=3,
            security_tier=SecurityTier.SELF_MANAGED,
            recommended_runtime_mode="deterministic",
        )

    async def healthcheck(self) -> HealthStatus:
        return HealthStatus(state=HealthState.HEALTHY, reason="echo-adapter-initialized")


def load_adapter(provider_id: str = "echo", **kwargs: Any) -> EchoRuntimeAdapter:
    """Factory entrypoint used by dynamic adapter loading."""
    return EchoRuntimeAdapter(provider_id=provider_id, **kwargs)
