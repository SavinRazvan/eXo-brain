"""
File: openai_agents_runtime.py
Path: src/runtime/openai_agents_runtime.py
Role: OpenAI runtime adapter implementation behind the provider-neutral contract.
Used By:
 - src/core/orchestrator.py
Depends On:
 - src/runtime/runtime_adapter.py
 - src/runtime/capability_map.py
 - src/schemas/events.py
 - src/schemas/tool_io.py
Notes:
 - This file is the only intended location for OpenAI SDK integration details.
"""

from __future__ import annotations

import uuid
from typing import Any, AsyncIterator

from src.runtime.capability_map import HealthState, HealthStatus, ProviderCapabilityMap, SecurityTier
from src.runtime.runtime_adapter import RuntimeAdapter, SessionHandle
from src.schemas.events import RuntimeEvent
from src.schemas.tool_io import RiskTier, ToolCallContext, ToolResult


class OpenAIAgentsRuntimeAdapter(RuntimeAdapter):
    def __init__(self, provider_id: str = "openai") -> None:
        self._provider_id = provider_id
        self._sessions: set[str] = set()

    async def start_session(
        self,
        session_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> SessionHandle:
        self._sessions.add(session_id)
        return SessionHandle(
            session_id=session_id,
            provider_id=self._provider_id,
            metadata=metadata or {},
        )

    async def run_turn(
        self,
        session_id: str,
        user_input: str,
        context: dict[str, Any],
    ) -> AsyncIterator[RuntimeEvent]:
        context = context if isinstance(context, dict) else {}
        run_id = str(context.get("run_id", f"run_{uuid.uuid4().hex[:8]}"))
        correlation_id = str(context.get("correlation_id", run_id))
        try:
            if not isinstance(user_input, str):
                raise ValueError("user_input must be a string")

            planned_call = context.get("planned_tool_call")
            if planned_call:
                if not isinstance(planned_call, dict):
                    raise ValueError("planned_tool_call must be an object")
                tool_name = str(planned_call.get("tool_name", "")).strip()
                if not tool_name:
                    raise ValueError("planned_tool_call.tool_name is required")
                call = ToolCallContext(
                    schema_version="1.0",
                    call_id=str(planned_call.get("call_id", f"tc_{uuid.uuid4().hex[:8]}")),
                    session_id=session_id,
                    run_id=run_id,
                    job_id=str(context.get("job_id", "job_local")),
                    task_id=str(context.get("task_id", "task_local")),
                    agent_id=str(context.get("agent_id", "agent_default")),
                    provider_id=self._provider_id,
                    tool_name=tool_name,
                    arguments=dict(planned_call.get("arguments", {})),
                    identity_subject=str((context.get("identity") or {}).get("subject", "")),
                    identity_roles=[
                        str(role)
                        for role in ((context.get("identity") or {}).get("roles", []) or [])
                        if str(role).strip()
                    ],
                    risk_tier=RiskTier(str(planned_call.get("risk_tier", "low"))),
                    is_state_changing=bool(planned_call.get("is_state_changing", False)),
                    timestamp_utc=str(context.get("timestamp_utc", "")),
                )
                yield RuntimeEvent.tool_intent(
                    session_id=session_id,
                    run_id=run_id,
                    call=call,
                    correlation_id=correlation_id,
                )
                return

            yield RuntimeEvent.output_delta(
                session_id=session_id,
                run_id=run_id,
                text=f"openai-adapter-echo: {user_input}",
                correlation_id=correlation_id,
            )
            yield RuntimeEvent.run_complete(
                session_id=session_id,
                run_id=run_id,
                output={"status": "completed", "provider_id": self._provider_id},
                correlation_id=correlation_id,
            )
        except Exception as exc:  # pragma: no cover - defensive adapter boundary
            yield RuntimeEvent.error(
                session_id=session_id,
                run_id=run_id,
                code="RUNTIME_TURN_ERROR",
                message=str(exc),
                correlation_id=correlation_id,
            )

    async def submit_tool_results(
        self,
        session_id: str,
        run_id: str,
        tool_results: list[ToolResult],
    ) -> AsyncIterator[RuntimeEvent]:
        correlation_id = run_id
        try:
            if not isinstance(tool_results, list):
                raise ValueError("tool_results must be a list")
            yield RuntimeEvent.output_delta(
                session_id=session_id,
                run_id=run_id,
                text=f"processed {len(tool_results)} tool result(s)",
                correlation_id=correlation_id,
            )
            yield RuntimeEvent.run_complete(
                session_id=session_id,
                run_id=run_id,
                output={
                    "status": "completed",
                    "tool_results_count": len(tool_results),
                    "provider_id": self._provider_id,
                },
                correlation_id=correlation_id,
            )
        except Exception as exc:  # pragma: no cover - defensive adapter boundary
            yield RuntimeEvent.error(
                session_id=session_id,
                run_id=run_id,
                code="RUNTIME_TOOL_RESULT_ERROR",
                message=str(exc),
                correlation_id=correlation_id,
            )

    def get_capabilities(self) -> ProviderCapabilityMap:
        return ProviderCapabilityMap(
            provider_id=self._provider_id,
            supports_agents_sdk_native=True,
            supports_openai_compatible_api=False,
            supports_streaming=True,
            supports_function_calling=True,
            supports_structured_output=True,
            supports_handoffs=True,
            reliability_score=5,
            security_tier=SecurityTier.MANAGED_VENDOR,
            recommended_runtime_mode="hybrid",
        )

    async def healthcheck(self) -> HealthStatus:
        return HealthStatus(state=HealthState.HEALTHY, reason="adapter-initialized")
