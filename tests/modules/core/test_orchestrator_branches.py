"""
File: test_orchestrator_branches.py
Path: tests/modules/core/test_orchestrator_branches.py
Role: Branch-complete tests for orchestrator deny/native/handoff helper paths.
Used By:
 - pytest
Depends On:
 - src/core/orchestrator.py
 - src/schemas/events.py
 - src/schemas/tool_io.py
Notes:
 - Uses lightweight runtime and agent doubles to hit edge branches.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any, AsyncIterator

from src.agents.contracts import AgentCapabilityTag
from src.core.orchestrator import Orchestrator
from src.policies.middleware import PolicyMiddleware
from src.runtime.capability_map import HealthState, HealthStatus, ProviderCapabilityMap
from src.runtime.runtime_adapter import RuntimeAdapter, SessionHandle
from src.schemas.events import RuntimeEvent, RuntimeEventType
from src.schemas.tool_io import (
    PolicyAction,
    PolicyDecision,
    RiskTier,
    ToolCallContext,
    ToolExecutionMode,
    ToolResult,
    ToolStatus,
)
from src.tools.executor import DeterministicToolExecutor
from src.tools.registry import ToolDescriptor, ToolRegistry


def _call_context(*, risk: RiskTier = RiskTier.LOW, state_changing: bool = False) -> ToolCallContext:
    return ToolCallContext(
        schema_version="1.0",
        call_id="call_o_1",
        session_id="sess_o_1",
        run_id="run_o_1",
        job_id="job_o_1",
        task_id="task_o_1",
        agent_id="agent_o_1",
        provider_id="provider_o_1",
        tool_name="echo_tool",
        arguments={"value": 1},
        risk_tier=risk,
        is_state_changing=state_changing,
    )


class _RuntimeAdapterDouble(RuntimeAdapter):
    def __init__(self, *, call: ToolCallContext) -> None:
        self._call = call
        self.submitted: list[ToolResult] = []
        self.started = 0

    async def start_session(self, session_id: str, metadata: dict[str, Any] | None = None) -> SessionHandle:
        self.started += 1
        return SessionHandle(session_id=session_id, provider_id="provider_o_1", metadata=metadata or {})

    async def run_turn(
        self,
        session_id: str,
        user_input: str,
        context: dict[str, Any],
    ) -> AsyncIterator[RuntimeEvent]:
        _ = user_input
        _ = context
        yield RuntimeEvent.tool_intent(session_id=session_id, run_id="run_o_1", call=self._call, correlation_id="corr_o_1")

    async def submit_tool_results(
        self,
        session_id: str,
        run_id: str,
        tool_results: list[ToolResult],
    ) -> AsyncIterator[RuntimeEvent]:
        self.submitted.extend(tool_results)
        yield RuntimeEvent.run_complete(session_id=session_id, run_id=run_id, output={"ok": True}, correlation_id="corr_o_1")

    def get_capabilities(self) -> ProviderCapabilityMap:
        return ProviderCapabilityMap(provider_id="provider_o_1")

    async def healthcheck(self) -> HealthStatus:
        return HealthStatus(state=HealthState.HEALTHY)


class _DenyPolicy(PolicyMiddleware):
    def before_tool_call(self, context: ToolCallContext) -> PolicyDecision:
        _ = context
        return PolicyDecision(
            schema_version="1.0",
            decision=PolicyAction.DENY,
            reason_code="DENY_FOR_TEST",
            message="blocked in test",
            enforced_mode=ToolExecutionMode.DETERMINISTIC,
        )

    def after_tool_call(self, result: ToolResult) -> ToolResult:
        return result

    def before_output(self, output: dict[str, object]) -> dict[str, object]:
        return output


class _AllowPolicy(PolicyMiddleware):
    def before_tool_call(self, context: ToolCallContext) -> PolicyDecision:
        _ = context
        return PolicyDecision(
            schema_version="1.0",
            decision=PolicyAction.ALLOW,
            reason_code="ALLOW_FOR_TEST",
            message="allowed in test",
            enforced_mode=ToolExecutionMode.DETERMINISTIC,
        )

    def after_tool_call(self, result: ToolResult) -> ToolResult:
        return result

    def before_output(self, output: dict[str, object]) -> dict[str, object]:
        return output


class _ByocLikeAdapter:
    backend_id = "byoc_pull_worker_runtime"
    drain_progress_events = 123  # Intentionally non-callable to hit defensive branch.

    def execute(self, call, descriptor):
        _ = call
        return ToolResult(
            schema_version="1.0",
            call_id="call_o_1",
            tool_name=descriptor.name,
            status=ToolStatus.SUCCESS,
            result={"value": {"ok": True}},
        )


def _collect(orchestrator: Orchestrator, *, context: dict[str, Any] | None = None) -> list[RuntimeEvent]:
    async def _run() -> list[RuntimeEvent]:
        out: list[RuntimeEvent] = []
        async for event in orchestrator.run_turn("sess_o_1", "input", context or {}):
            out.append(event)
        return out

    return asyncio.run(_run())


def test_orchestrator_deny_branch_emits_failed_progress_and_submits_blocked_result() -> None:
    registry = ToolRegistry()
    registry.register(ToolDescriptor(name="echo_tool", handler=lambda value: value))
    adapter = _RuntimeAdapterDouble(call=_call_context())
    orchestrator = Orchestrator(
        runtime_adapter=adapter,
        policy_middleware=_DenyPolicy(),
        tool_executor=DeterministicToolExecutor(registry=registry, policy=_DenyPolicy()),
    )
    events = _collect(orchestrator, context={"run_id": "run_o_1"})
    progress_states = [e.payload.get("state") for e in events if e.event_type == RuntimeEventType.TOOL_PROGRESS]
    assert progress_states == ["queued", "failed"]
    assert len(adapter.submitted) == 1
    assert adapter.submitted[0].status == ToolStatus.BLOCKED


def test_orchestrator_provider_native_passthrough_for_low_risk_tools(monkeypatch) -> None:
    registry = ToolRegistry()
    registry.register(ToolDescriptor(name="echo_tool", handler=lambda value: value))
    adapter = _RuntimeAdapterDouble(call=_call_context(risk=RiskTier.LOW, state_changing=False))
    policy = _AllowPolicy()
    orchestrator = Orchestrator(
        runtime_adapter=adapter,
        policy_middleware=policy,
        tool_executor=DeterministicToolExecutor(registry=registry, policy=policy),
    )
    monkeypatch.setattr("src.core.orchestrator.select_execution_mode", lambda **_: ToolExecutionMode.PROVIDER_NATIVE)
    events = _collect(orchestrator, context={"run_id": "run_o_1"})
    assert any(event.event_type == RuntimeEventType.TOOL_INTENT for event in events)


def test_orchestrator_terminal_state_and_progress_guard_branches() -> None:
    registry = ToolRegistry()
    registry.register(ToolDescriptor(name="echo_tool", handler=lambda value: value))
    policy = _AllowPolicy()
    runtime = _RuntimeAdapterDouble(call=_call_context(risk=RiskTier.HIGH, state_changing=True))
    executor = DeterministicToolExecutor(
        registry=registry,
        policy=policy,
        execution_adapter=_ByocLikeAdapter(),  # type: ignore[arg-type]
        enable_hosted_runtime=True,
    )
    orchestrator = Orchestrator(runtime_adapter=runtime, policy_middleware=policy, tool_executor=executor)

    assert orchestrator._terminal_tool_state(ToolStatus.TIMEOUT) == "timed_out"
    assert orchestrator._terminal_tool_state(ToolStatus.CANCELLED) == "cancelled"
    assert orchestrator._terminal_tool_state(ToolStatus.ERROR) == "failed"
    assert orchestrator._emit_adapter_progress(
        session_id="sess",
        run_id="run",
        correlation_id="corr",
        call_id="call",
        adapter=_ByocLikeAdapter(),
    ) == []

    _collect(orchestrator, context={"run_id": "run_o_1"})


def test_orchestrator_emit_adapter_progress_defensive_guards() -> None:
    """Each defensive guard in _emit_adapter_progress returns [] / skips silently for malformed adapter output."""
    registry = ToolRegistry()
    registry.register(ToolDescriptor(name="echo_tool", handler=lambda value: value))
    policy = _AllowPolicy()
    runtime = _RuntimeAdapterDouble(call=_call_context())
    orchestrator = Orchestrator(
        runtime_adapter=runtime,
        policy_middleware=policy,
        tool_executor=DeterministicToolExecutor(registry=registry, policy=policy),
    )

    def _emit(adapter_obj: Any) -> list[RuntimeEvent]:
        return orchestrator._emit_adapter_progress(
            session_id="sess",
            run_id="run",
            correlation_id="corr",
            call_id="call",
            adapter=adapter_obj,
        )

    class _ReturnsNone:
        def drain_progress_events(self, _call_id: str) -> None:
            return None

    class _ReturnsString:
        def drain_progress_events(self, _call_id: str) -> str:
            return "not iterable as progress"

    class _ReturnsBytes:
        def drain_progress_events(self, _call_id: str) -> bytes:
            return b"raw"

    class _ReturnsNonIterable:
        def drain_progress_events(self, _call_id: str) -> int:
            return 42  # type: ignore[return-value]

    class _ReturnsNonMappingItems:
        def drain_progress_events(self, _call_id: str) -> list[Any]:
            return ["progress-as-string", 7, ("tuple", "item")]

    assert _emit(_ReturnsNone()) == []
    assert _emit(_ReturnsString()) == []
    assert _emit(_ReturnsBytes()) == []
    assert _emit(_ReturnsNonIterable()) == []
    assert _emit(_ReturnsNonMappingItems()) == []


def test_orchestrator_handoff_error_matrix() -> None:
    class _AgentRegistryDouble:
        def __init__(self) -> None:
            self.known = {"agent-ok"}

        def get(self, agent_id: str):
            if agent_id not in self.known:
                raise KeyError(agent_id)
            return SimpleNamespace(agent_id=agent_id)

        def resolve_handoff_target(self, source_agent_id: str, target_role: str | None, required_capability):
            _ = source_agent_id
            _ = target_role
            _ = required_capability
            return None

    policy = _AllowPolicy()
    registry = ToolRegistry()
    registry.register(ToolDescriptor(name="echo_tool", handler=lambda value: value))
    orchestrator = Orchestrator(
        runtime_adapter=_RuntimeAdapterDouble(call=_call_context()),
        policy_middleware=policy,
        tool_executor=DeterministicToolExecutor(registry=registry, policy=policy),
        agent_registry=_AgentRegistryDouble(),  # type: ignore[arg-type]
    )

    invalid_handoff = orchestrator._apply_agent_handoff({"handoff": "bad", "agent_id": "agent-ok"})
    assert invalid_handoff is not None
    assert invalid_handoff["code"] == "ORCH_HANDOFF_INVALID"

    missing_source = orchestrator._apply_agent_handoff({"handoff": {}})
    assert missing_source is not None
    assert missing_source["code"] == "ORCH_HANDOFF_SOURCE_AGENT_MISSING"

    unknown_source = orchestrator._apply_agent_handoff({"handoff": {}, "agent_id": "ghost"})
    assert unknown_source is not None
    assert unknown_source["code"] == "ORCH_HANDOFF_SOURCE_AGENT_UNKNOWN"

    invalid_capability = orchestrator._apply_agent_handoff(
        {"handoff": {"required_capability": "bad-cap"}, "agent_id": "agent-ok"}
    )
    assert invalid_capability is not None
    assert invalid_capability["code"] == "ORCH_HANDOFF_REQUIRED_CAPABILITY_INVALID"

    route_denied = orchestrator._apply_agent_handoff(
        {"handoff": {"target_role": "reviewer"}, "agent_id": "agent-ok"}
    )
    assert route_denied is not None
    assert route_denied["code"] == "ORCH_HANDOFF_ROUTE_DENIED"

    target_missing = orchestrator._apply_agent_handoff({"handoff": {}, "agent_id": "agent-ok"})
    assert target_missing is not None
    assert target_missing["code"] == "ORCH_HANDOFF_TARGET_NOT_FOUND"

    assert orchestrator._parse_required_capability(AgentCapabilityTag.TOOL_USE.value) == AgentCapabilityTag.TOOL_USE
