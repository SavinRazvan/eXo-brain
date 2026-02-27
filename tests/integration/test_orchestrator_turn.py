"""
File: test_orchestrator_turn.py
Path: tests/integration/test_orchestrator_turn.py
Role: Integration test for one-turn orchestrator flow with deterministic tool execution.
Used By:
 - pytest
Depends On:
 - src/core/orchestrator.py
 - src/runtime/openai_agents_runtime.py
 - src/policies/middleware.py
 - src/tools/registry.py
 - src/tools/executor.py
Notes:
 - Validates tool-intent handoff through deterministic path and submit_tool_results.
"""

from src.core.orchestrator import Orchestrator
from src.policies.middleware import DeterministicFirstPolicyMiddleware
from src.runtime.openai_agents_runtime import OpenAIAgentsRuntimeAdapter
from src.schemas.events import RuntimeEventType
from src.schemas.tool_io import RiskTier
from src.tools.executor import DeterministicToolExecutor
from src.tools.registry import ToolDescriptor, ToolRegistry


async def _collect_events(orchestrator: Orchestrator, session_id: str, context: dict) -> list:
    events = []
    async for event in orchestrator.run_turn(session_id=session_id, user_input="execute", context=context):
        events.append(event)
    return events


def test_orchestrator_executes_high_risk_tool_deterministically() -> None:
    registry = ToolRegistry()
    registry.register(
        ToolDescriptor(
            name="multiply",
            handler=lambda a, b: a * b,
            risk_tier=RiskTier.HIGH,
            is_state_changing=True,
        )
    )

    orchestrator = Orchestrator(
        runtime_adapter=OpenAIAgentsRuntimeAdapter(),
        policy_middleware=DeterministicFirstPolicyMiddleware(),
        tool_executor=DeterministicToolExecutor(registry=registry, policy=DeterministicFirstPolicyMiddleware()),
    )

    context = {
        "run_id": "run_integration",
        "job_id": "job_integration",
        "task_id": "task_integration",
        "agent_id": "agent_executor",
        "planned_tool_call": {
            "call_id": "tc_integration",
            "tool_name": "multiply",
            "arguments": {"a": 4, "b": 5},
            "risk_tier": RiskTier.HIGH.value,
            "is_state_changing": True,
        },
    }

    import asyncio

    events = asyncio.run(_collect_events(orchestrator, session_id="sess_integration", context=context))
    event_types = [event.event_type for event in events]
    assert RuntimeEventType.OUTPUT_DELTA in event_types
    assert RuntimeEventType.RUN_COMPLETE in event_types
