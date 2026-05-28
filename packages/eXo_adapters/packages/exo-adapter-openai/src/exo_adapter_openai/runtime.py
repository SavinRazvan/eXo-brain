"""
File: runtime.py
Path: packages/exo-adapter-openai/src/exo_adapter_openai/runtime.py
Role: Standalone OpenAI runtime adapter entrypoint for provider package consumers.
Used By:
 - dynamic adapter loaders
Depends On:
 - exo_brain_core_contracts
 - exo_adapter_openai/tool_wiring.py
Notes:
 - Keeps package portable by avoiding monorepo-only imports.
"""

from __future__ import annotations

import os
import uuid
from typing import Any, AsyncIterator, cast

from exo_brain_core_contracts import (
    HealthState,
    HealthStatus,
    ProviderCapabilityMap,
    RiskTier,
    RuntimeAdapter,
    RuntimeEvent,
    RuntimeEventType,
    SecurityTier,
    SessionHandle,
    ToolCallContext,
    ToolResult,
    ToolStatus,
)

from exo_adapter_openai.tool_wiring import build_agent_tools


def _coerce_risk_tier(value: Any) -> RiskTier:
    if isinstance(value, RiskTier):
        return value
    candidate = str(getattr(value, "value", value)).strip().lower()
    for tier in RiskTier:
        if tier.value == candidate:
            return tier
    return RiskTier.LOW


def _tool_intent_event(
    *,
    session_id: str,
    run_id: str,
    call: ToolCallContext,
    correlation_id: str,
) -> RuntimeEvent:
    return RuntimeEvent(
        event_type=RuntimeEventType.TOOL_INTENT,
        session_id=session_id,
        run_id=run_id,
        correlation_id=correlation_id or run_id,
        tool_call=call,
    )


def _output_delta_event(
    *,
    session_id: str,
    run_id: str,
    text: str,
    correlation_id: str,
) -> RuntimeEvent:
    return RuntimeEvent(
        event_type=RuntimeEventType.OUTPUT_DELTA,
        session_id=session_id,
        run_id=run_id,
        correlation_id=correlation_id or run_id,
        payload={"text": text},
    )


def _run_complete_event(
    *,
    session_id: str,
    run_id: str,
    output: dict[str, Any] | None,
    correlation_id: str,
) -> RuntimeEvent:
    return RuntimeEvent(
        event_type=RuntimeEventType.RUN_COMPLETE,
        session_id=session_id,
        run_id=run_id,
        correlation_id=correlation_id or run_id,
        payload=output or {},
    )


def _format_tool_results_for_model(tool_results: list[ToolResult]) -> str:
    lines: list[str] = []
    for item in tool_results:
        status = getattr(item.status, "value", item.status)
        if item.status == ToolStatus.SUCCESS or str(status).lower() == ToolStatus.SUCCESS.value:
            payload = item.result or {}
            value = payload.get("value", payload) if isinstance(payload, dict) else payload
            lines.append(f"- {item.tool_name} ({item.call_id}): success → {value!r}")
        else:
            message = getattr(item.error, "message", "") or str(item.error)
            lines.append(f"- {item.tool_name} ({item.call_id}): {status} → {message}")
    return "\n".join(lines) if lines else "(no tool results)"


def _error_event(
    *,
    session_id: str,
    run_id: str,
    code: str,
    message: str,
    correlation_id: str,
) -> RuntimeEvent:
    return RuntimeEvent(
        event_type=RuntimeEventType.ERROR,
        session_id=session_id,
        run_id=run_id,
        correlation_id=correlation_id or run_id,
        payload={"code": code, "message": message},
    )


class OpenAIAgentsRuntimeAdapter(RuntimeAdapter):
    """OpenAI Agents SDK adapter package entrypoint."""

    def __init__(
        self,
        provider_id: str = "openai",
        tool_registry: Any | None = None,
        tool_executor: Any | None = None,
    ) -> None:
        self._provider_id = provider_id
        self._tool_registry = tool_registry
        self._tool_executor = tool_executor
        self._session_metadata: dict[str, dict[str, Any]] = {}
        self._sessions: set[str] = set()

    def _delegating_tools_enabled(self) -> bool:
        return (
            self._tool_registry is not None
            and self._tool_executor is not None
            and bool(os.getenv("OPENAI_API_KEY"))
        )

    async def start_session(
        self,
        session_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> SessionHandle:
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
        session_meta = self._session_metadata.setdefault(session_id, {})
        session_meta["last_user_input"] = user_input

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
                    identity_tenant_id=str((context.get("identity") or {}).get("tenant_id", "")),
                    identity_subject=str((context.get("identity") or {}).get("subject", "")),
                    identity_roles=[
                        str(role)
                        for role in ((context.get("identity") or {}).get("roles", []) or [])
                        if str(role).strip()
                    ],
                    risk_tier=_coerce_risk_tier(planned_call.get("risk_tier", "low")),
                    is_state_changing=bool(planned_call.get("is_state_changing", False)),
                    timestamp_utc=str(context.get("timestamp_utc", "")),
                )
                yield _tool_intent_event(
                    session_id=session_id,
                    run_id=run_id,
                    call=call,
                    correlation_id=correlation_id,
                )
                return

            delegating = self._delegating_tools_enabled()
            if delegating:
                agent_id = str(session_meta.get("agent_id", "exo-agent"))

                from agents import Agent, Runner  # type: ignore[import-not-found,import-untyped]
                from agents.items import (  # type: ignore[import-not-found,import-untyped]
                    ItemHelpers,
                    MessageOutputItem,
                    ToolCallItem,
                    ToolCallOutputItem,
                )
                from agents.stream_events import RunItemStreamEvent  # type: ignore[import-not-found,import-untyped]

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
                    instructions=str(session_meta.get("instructions", "")),
                    model=str(session_meta.get("model", "gpt-4o-mini")),
                    tools=cast(Any, tools),
                )

                result = Runner.run_streamed(agent, user_input)
                async for event in result.stream_events():
                    if not isinstance(event, RunItemStreamEvent):
                        continue
                    item = event.item
                    if isinstance(item, MessageOutputItem):
                        text = ItemHelpers.text_message_output(item)
                        yield _output_delta_event(
                            session_id=session_id,
                            run_id=run_id,
                            text=text,
                            correlation_id=correlation_id,
                        )
                    elif isinstance(item, ToolCallItem):
                        # Delegating tools: FunctionTool bodies call the executor; skip TOOL_INTENT.
                        pass
                    elif isinstance(item, ToolCallOutputItem):
                        # Tool results are emitted through deterministic tool wiring.
                        pass

                final_output = result.final_output or ""
                yield _run_complete_event(
                    session_id=session_id,
                    run_id=run_id,
                    output={"status": "completed", "output": str(final_output), "provider_id": self._provider_id},
                    correlation_id=correlation_id,
                )
                return

            yield _output_delta_event(
                session_id=session_id,
                run_id=run_id,
                text=f"openai-adapter-echo: {user_input}",
                correlation_id=correlation_id,
            )
            yield _run_complete_event(
                session_id=session_id,
                run_id=run_id,
                output={"status": "completed", "provider_id": self._provider_id},
                correlation_id=correlation_id,
            )
        except Exception as exc:
            yield _error_event(
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

            formatted = _format_tool_results_for_model(tool_results)
            session_meta = self._session_metadata.get(session_id, {})
            last_user_input = str(session_meta.get("last_user_input", "")).strip()

            if self._delegating_tools_enabled():
                from agents import Agent, Runner  # type: ignore[import-not-found,import-untyped]

                agent_id = str(session_meta.get("agent_id", "exo-agent"))
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
                    instructions=str(session_meta.get("instructions", "You are a helpful assistant.")),
                    model=str(session_meta.get("model", "gpt-4o-mini")),
                    tools=cast(Any, tools),
                )
                prompt_parts = ["Tool execution finished.", f"Results:\n{formatted}"]
                if last_user_input:
                    prompt_parts.insert(0, f"The user asked: {last_user_input}")
                prompt_parts.append("Provide a concise final answer to the user.")
                continuation = await Runner.run(agent, "\n\n".join(prompt_parts))
                final_output = str(getattr(continuation, "final_output", "") or "")
                if final_output:
                    yield _output_delta_event(
                        session_id=session_id,
                        run_id=run_id,
                        text=final_output,
                        correlation_id=correlation_id,
                    )
                yield _run_complete_event(
                    session_id=session_id,
                    run_id=run_id,
                    output={
                        "status": "completed",
                        "output": final_output,
                        "tool_results_count": len(tool_results),
                        "provider_id": self._provider_id,
                    },
                    correlation_id=correlation_id,
                )
                return

            yield _output_delta_event(
                session_id=session_id,
                run_id=run_id,
                text=formatted,
                correlation_id=correlation_id,
            )
            yield _run_complete_event(
                session_id=session_id,
                run_id=run_id,
                output={
                    "status": "completed",
                    "tool_results_count": len(tool_results),
                    "tool_results_summary": formatted,
                    "provider_id": self._provider_id,
                },
                correlation_id=correlation_id,
            )
        except Exception as exc:
            yield _error_event(
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


def load_adapter(provider_id: str = "openai", **kwargs: Any) -> OpenAIAgentsRuntimeAdapter:
    """Factory entrypoint used by dynamic adapter loading."""
    return OpenAIAgentsRuntimeAdapter(provider_id=provider_id, **kwargs)
