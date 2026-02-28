"""
File: test_multi_adapter_workflow_parity.py
Path: tests/integration/test_multi_adapter_workflow_parity.py
Role: Integration parity test for workflow behavior across two runtime adapters.
Used By:
 - pytest
Depends On:
 - src/core/orchestrator.py
 - src/runtime/runtime_adapter.py
 - src/runtime/openai_agents_runtime.py
 - src/tools/executor.py
Notes:
 - Confirms provider-neutral flow yields stable event envelope semantics.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from src.core.orchestrator import Orchestrator
from src.policies.middleware import DeterministicFirstPolicyMiddleware
from src.runtime.custom_runtime import CustomRuntimeAdapter
from src.runtime.capability_map import HealthState, HealthStatus, ProviderCapabilityMap
from src.runtime.openai_agents_runtime import OpenAIAgentsRuntimeAdapter
from src.runtime.openai_compatible_runtime import OpenAICompatibleRuntimeAdapter
from src.runtime.runtime_adapter import RuntimeAdapter, SessionHandle
from src.schemas.events import RuntimeEvent
from src.schemas.tool_io import ToolResult
from src.tools.executor import DeterministicToolExecutor
from src.tools.registry import ToolDescriptor, ToolRegistry


class MockRuntimeAdapter(RuntimeAdapter):
    async def start_session(self, session_id: str, metadata: dict[str, Any] | None = None) -> SessionHandle:
        return SessionHandle(session_id=session_id, provider_id="mock", metadata=metadata or {})

    async def run_turn(self, session_id: str, user_input: str, context: dict[str, Any]) -> AsyncIterator[RuntimeEvent]:
        run_id = str(context.get("run_id", "run_mock"))
        yield RuntimeEvent.output_delta(session_id=session_id, run_id=run_id, text=f"mock-echo: {user_input}")
        yield RuntimeEvent.run_complete(session_id=session_id, run_id=run_id, output={"status": "completed", "provider_id": "mock"})

    async def submit_tool_results(
        self, session_id: str, run_id: str, tool_results: list[ToolResult]
    ) -> AsyncIterator[RuntimeEvent]:
        yield RuntimeEvent.run_complete(
            session_id=session_id, run_id=run_id, output={"status": "completed", "tool_results_count": len(tool_results)}
        )

    def get_capabilities(self) -> ProviderCapabilityMap:
        return ProviderCapabilityMap(provider_id="mock", reliability_score=5)

    async def healthcheck(self) -> HealthStatus:
        return HealthStatus(state=HealthState.HEALTHY, reason="mock")


async def _collect(orchestrator: Orchestrator, session_id: str, context: dict[str, Any]) -> list[RuntimeEvent]:
    output = []
    async for event in orchestrator.run_turn(session_id=session_id, user_input="ping", context=context):
        output.append(event)
    return output


def _build_orchestrator(runtime_adapter: RuntimeAdapter) -> Orchestrator:
    registry = ToolRegistry()
    registry.register(ToolDescriptor(name="noop", handler=lambda: "ok"))
    policy = DeterministicFirstPolicyMiddleware()
    executor = DeterministicToolExecutor(registry=registry, policy=policy)
    return Orchestrator(runtime_adapter=runtime_adapter, policy_middleware=policy, tool_executor=executor)


def test_multi_adapter_event_parity_for_simple_turn() -> None:
    openai_events = asyncio.run(_collect(_build_orchestrator(OpenAIAgentsRuntimeAdapter()), "sess_a", {"run_id": "run_a"}))
    compatible_events = asyncio.run(
        _collect(_build_orchestrator(OpenAICompatibleRuntimeAdapter()), "sess_b", {"run_id": "run_b"})
    )
    custom_events = asyncio.run(_collect(_build_orchestrator(CustomRuntimeAdapter()), "sess_c", {"run_id": "run_c"}))
    mock_events = asyncio.run(_collect(_build_orchestrator(MockRuntimeAdapter()), "sess_d", {"run_id": "run_d"}))

    assert [event.event_type.value for event in openai_events] == ["output_delta", "run_complete"]
    assert [event.event_type.value for event in compatible_events] == ["output_delta", "run_complete"]
    assert [event.event_type.value for event in custom_events] == ["output_delta", "run_complete"]
    assert [event.event_type.value for event in mock_events] == ["output_delta", "run_complete"]
