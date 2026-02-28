"""
File: orchestrator.py
Path: src/core/orchestrator.py
Role: Orchestrates one-turn execution across runtime adapter, policies, and tool runtime.
Used By:
 - integration host adapters (future)
 - tests/integration/test_background_agent_pipeline.py (future)
Depends On:
 - src/agents/registry.py
 - src/runtime/runtime_adapter.py
 - src/runtime/mode_selector.py
 - src/policies/middleware.py
 - src/tools/executor.py
 - src/schemas/events.py
 - src/schemas/tool_io.py
Notes:
 - Core must remain provider-neutral and avoid provider SDK imports.
"""

from __future__ import annotations

from typing import Any, AsyncIterator

from src.agents.contracts import AgentCapabilityTag
from src.agents.registry import AgentRegistry
from src.policies.middleware import PolicyMiddleware
from src.runtime.mode_selector import select_execution_mode
from src.runtime.runtime_adapter import RuntimeAdapter
from src.schemas.events import RuntimeEvent, RuntimeEventType
from src.schemas.tool_io import PolicyAction, RiskTier, ToolCallContext, ToolExecutionMode, blocked_result
from src.tools.executor import DeterministicToolExecutor


class Orchestrator:
    def __init__(
        self,
        runtime_adapter: RuntimeAdapter,
        policy_middleware: PolicyMiddleware,
        tool_executor: DeterministicToolExecutor,
        agent_registry: AgentRegistry | None = None,
    ) -> None:
        self._runtime_adapter = runtime_adapter
        self._policy = policy_middleware
        self._tool_executor = tool_executor
        self._agent_registry = agent_registry

    async def run_turn(
        self,
        session_id: str,
        user_input: str,
        context: dict,
    ) -> AsyncIterator[RuntimeEvent]:
        resolved_context = dict(context)
        handoff_error = self._apply_agent_handoff(resolved_context)
        if handoff_error is not None:
            yield RuntimeEvent.error(
                session_id=session_id,
                run_id=str(resolved_context.get("run_id", "run_unknown")),
                code=handoff_error["code"],
                message=handoff_error["message"],
                correlation_id=str(resolved_context.get("correlation_id", "")),
            )
            return

        await self._runtime_adapter.start_session(
            session_id=session_id,
            metadata=resolved_context.get("session_metadata"),
        )

        async for event in self._runtime_adapter.run_turn(
            session_id=session_id,
            user_input=user_input,
            context=resolved_context,
        ):
            if event.event_type != RuntimeEventType.TOOL_INTENT or event.tool_call is None:
                yield self._apply_output_policy(event)
                continue

            decision = self._policy.before_tool_call(event.tool_call)
            if decision.decision != PolicyAction.ALLOW:
                blocked = self._tool_executor.execute(event.tool_call)
                async for follow_up in self._runtime_adapter.submit_tool_results(
                    session_id=session_id,
                    run_id=event.run_id,
                    tool_results=[blocked],
                ):
                    yield self._apply_output_policy(follow_up)
                continue

            mode = select_execution_mode(
                tool_call=event.tool_call,
                capability_map=self._runtime_adapter.get_capabilities(),
                policy_decision=decision,
            )
            if mode == ToolExecutionMode.DETERMINISTIC:
                result = self._tool_executor.execute(event.tool_call)
                async for follow_up in self._runtime_adapter.submit_tool_results(
                    session_id=session_id,
                    run_id=event.run_id,
                    tool_results=[result],
                ):
                    yield self._apply_output_policy(follow_up)
            else:
                if self._requires_deterministic_envelope(event.tool_call):
                    blocked = blocked_result(
                        context=event.tool_call,
                        reason_code="PROVIDER_NATIVE_STATE_CHANGE_BLOCKED",
                        message=(
                            "Provider-native execution is blocked for state-changing or high-impact operations; "
                            "a deterministic envelope is enforced."
                        ),
                    )
                    async for follow_up in self._runtime_adapter.submit_tool_results(
                        session_id=session_id,
                        run_id=event.run_id,
                        tool_results=[blocked],
                    ):
                        yield self._apply_output_policy(follow_up)
                    continue
                # Provider-native execution path is left to adapter behavior.
                yield self._apply_output_policy(event)

    def _apply_output_policy(self, event: RuntimeEvent) -> RuntimeEvent:
        if event.event_type in {RuntimeEventType.OUTPUT_DELTA, RuntimeEventType.RUN_COMPLETE}:
            event.payload = self._policy.before_output(dict(event.payload))
        return event

    def _requires_deterministic_envelope(self, tool_call: ToolCallContext) -> bool:
        return tool_call.is_state_changing or tool_call.risk_tier in {RiskTier.HIGH, RiskTier.CRITICAL}

    def _apply_agent_handoff(self, context: dict[str, Any]) -> dict[str, str] | None:
        if self._agent_registry is None:
            return None

        raw_handoff = context.get("handoff")
        if raw_handoff is None:
            return None
        if not isinstance(raw_handoff, dict):
            return {
                "code": "ORCH_HANDOFF_INVALID",
                "message": "handoff must be an object when provided.",
            }

        source_agent_id = str(context.get("agent_id", "")).strip()
        if not source_agent_id:
            return {
                "code": "ORCH_HANDOFF_SOURCE_AGENT_MISSING",
                "message": "agent_id is required for handoff routing.",
            }

        try:
            self._agent_registry.get(source_agent_id)
        except KeyError:
            return {
                "code": "ORCH_HANDOFF_SOURCE_AGENT_UNKNOWN",
                "message": f"Unknown handoff source agent '{source_agent_id}'.",
            }

        required_capability = self._parse_required_capability(raw_handoff.get("required_capability"))
        if isinstance(required_capability, dict):
            return required_capability

        target_role = str(raw_handoff.get("target_role", "")).strip() or None
        target_agent = self._agent_registry.resolve_handoff_target(
            source_agent_id=source_agent_id,
            target_role=target_role,
            required_capability=required_capability,
        )
        if target_agent is None:
            if target_role:
                return {
                    "code": "ORCH_HANDOFF_ROUTE_DENIED",
                    "message": (
                        f"No allowed handoff route from '{source_agent_id}' "
                        f"to role '{target_role}' (including fallback candidates)."
                    ),
                }
            return {
                "code": "ORCH_HANDOFF_TARGET_NOT_FOUND",
                "message": "No handoff target available for requested constraints.",
            }

        context["agent_id"] = target_agent.agent_id
        metadata = dict(context.get("session_metadata", {}))
        metadata["handoff"] = {
            "source_agent_id": source_agent_id,
            "target_agent_id": target_agent.agent_id,
            "target_role": target_agent.role,
            "reason": str(raw_handoff.get("reason", "unspecified")),
        }
        context["session_metadata"] = metadata
        return None

    def _parse_required_capability(
        self,
        raw_capability: Any,
    ) -> AgentCapabilityTag | dict[str, str] | None:
        if raw_capability in (None, ""):
            return None
        try:
            return AgentCapabilityTag(str(raw_capability))
        except ValueError:
            return {
                "code": "ORCH_HANDOFF_REQUIRED_CAPABILITY_INVALID",
                "message": f"Unknown required_capability '{raw_capability}'.",
            }
