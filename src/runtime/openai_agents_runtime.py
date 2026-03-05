"""
File: openai_agents_runtime.py
Path: src/runtime/openai_agents_runtime.py
Role: OpenAI Agents SDK runtime adapter — wires the SDK into the provider-neutral contract.
Used By:
 - src/runtime/tenant_runtime.py
 - src/core/orchestrator.py
Depends On:
 - src/runtime/runtime_adapter.py
 - src/runtime/tool_wiring.py
 - src/runtime/capability_map.py
 - src/schemas/events.py
 - src/tools/registry.py
 - src/tools/executor.py
Notes:
 - This file is the ONLY intended location for OpenAI Agents SDK integration.
 - Constructor takes (provider_id, tool_registry, tool_executor) — no TenantRuntimeContext
   reference to avoid circular dependency (Problem 1 fix).
 - start_session stores flat metadata dict — AgentSpec resolved by TenantRuntimeFactory
   before this call (Problem 4 fix).
 - run_turn calls build_agent_tools on every invocation for late binding (Problem 5 fix).
 - The stub path (planned_tool_call echo) is preserved for tests that do not set OPENAI_API_KEY.
"""

from __future__ import annotations

import uuid
from typing import Any, AsyncIterator

from src.runtime.capability_map import HealthState, HealthStatus, ProviderCapabilityMap, SecurityTier
from src.runtime.runtime_adapter import RuntimeAdapter, SessionHandle
from src.schemas.events import RuntimeEvent
from src.schemas.tool_io import RiskTier, ToolCallContext, ToolResult
from src.tools.executor import DeterministicToolExecutor
from src.tools.registry import ToolRegistry


class OpenAIAgentsRuntimeAdapter(RuntimeAdapter):
    """OpenAI Agents SDK adapter.

    When OPENAI_API_KEY is set and an Agent/Runner are available, real SDK calls are made.
    When tool_registry and tool_executor are not provided (legacy/test path), the adapter
    falls back to the echo stub behaviour to keep existing tests passing.
    """

    def __init__(
        self,
        provider_id: str = "openai",
        tool_registry: ToolRegistry | None = None,
        tool_executor: DeterministicToolExecutor | None = None,
    ) -> None:
        self._provider_id = provider_id
        self._tool_registry = tool_registry
        self._tool_executor = tool_executor
        self._session_metadata: dict[str, dict[str, Any]] = {}
        self._sessions: set[str] = set()

    async def start_session(
        self,
        session_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> SessionHandle:
        """Store agent metadata for later use in run_turn."""
        self._sessions.add(session_id)
        self._session_metadata[session_id] = metadata or {}
        return SessionHandle(
            session_id=session_id,
            provider_id=self._provider_id,
            metadata={},
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

            # ------------------------------------------------------------------
            # Legacy stub path: used by existing tests that inject planned_tool_call
            # ------------------------------------------------------------------
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
                    identity_tenant_id=str((context.get("identity") or {}).get("tenant_id", "")),
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

            # ------------------------------------------------------------------
            # Real SDK path: requires tool_registry + tool_executor + OPENAI_API_KEY
            # ------------------------------------------------------------------
            import os
            _has_api_key = bool(os.getenv("OPENAI_API_KEY"))
            if self._tool_registry is not None and self._tool_executor is not None and _has_api_key:
                session_meta = self._session_metadata.get(session_id, {})
                agent_id = session_meta.get("agent_id", "exo-agent")

                from agents import Agent, Runner
                from agents.stream_events import RawResponsesStreamEvent, RunItemStreamEvent
                from agents.items import MessageOutputItem, ToolCallItem, ToolCallOutputItem

                from src.runtime.tool_wiring import build_agent_tools

                tools = build_agent_tools(
                    tool_registry=self._tool_registry,
                    tool_executor=self._tool_executor,
                    session_id=session_id,
                    agent_id=agent_id,
                    provider_id=self._provider_id,
                    tenant_id=str(session_meta.get("tenant_id", "default")),
                )

                agent = Agent(
                    name=agent_id,
                    instructions=session_meta.get("instructions", ""),
                    model=session_meta.get("model", "gpt-4o-mini"),
                    tools=tools,
                )

                result = Runner.run_streamed(agent, user_input)
                async for event in result.stream_events():
                    if isinstance(event, RunItemStreamEvent):
                        item = event.item
                        if isinstance(item, MessageOutputItem):
                            from agents.items import ItemHelpers
                            text = ItemHelpers.text_message_output(item)
                            yield RuntimeEvent.output_delta(
                                session_id=session_id,
                                run_id=run_id,
                                text=text,
                                correlation_id=correlation_id,
                            )
                        elif isinstance(item, ToolCallItem):
                            raw = item.raw_item
                            yield RuntimeEvent.tool_intent(
                                session_id=session_id,
                                run_id=run_id,
                                call=ToolCallContext(
                                    schema_version="1.0",
                                    call_id=getattr(raw, "call_id", run_id),
                                    session_id=session_id,
                                    run_id=run_id,
                                    job_id="job_api",
                                    task_id="task_api",
                                    agent_id=agent_id,
                                    provider_id=self._provider_id,
                                    tool_name=getattr(raw, "name", ""),
                                    arguments={},
                                ),
                                correlation_id=correlation_id,
                            )
                        elif isinstance(item, ToolCallOutputItem):
                            pass  # result already yielded by tool_wiring executor

                final_output = result.final_output or ""
                yield RuntimeEvent.run_complete(
                    session_id=session_id,
                    run_id=run_id,
                    output={"status": "completed", "output": str(final_output), "provider_id": self._provider_id},
                    correlation_id=correlation_id,
                )
                return

            # ------------------------------------------------------------------
            # Fallback echo (no registry wired — used by legacy unit tests)
            # ------------------------------------------------------------------
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
        """Feed tool results back to the SDK session.

        In the delegating-wrapper pattern, tool execution happens inside on_invoke_tool
        during run_turn, so this method is only invoked by the orchestrator's stub/test
        path. It preserves the original two-event shape to keep existing tests passing.
        """
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
