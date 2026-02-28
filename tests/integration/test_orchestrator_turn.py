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
from src.policies.middleware import DeterministicFirstPolicyMiddleware, PolicyMiddleware
from src.runtime.openai_agents_runtime import OpenAIAgentsRuntimeAdapter
from src.schemas.events import RuntimeEventType
from src.schemas.tool_io import PolicyAction, PolicyDecision, RiskTier, ToolCallContext, ToolExecutionMode, ToolResult
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


class OutputGuardPolicy(PolicyMiddleware):
    def __init__(self) -> None:
        self.output_calls = 0

    def before_tool_call(self, context: ToolCallContext) -> PolicyDecision:
        return PolicyDecision(
            schema_version="1.0",
            decision=PolicyAction.ALLOW,
            reason_code="ALLOW_FOR_TEST",
            message="allowed",
            enforced_mode=ToolExecutionMode.DETERMINISTIC,
        )

    def after_tool_call(self, result: ToolResult) -> ToolResult:
        return result

    def before_output(self, output: dict[str, object]) -> dict[str, object]:
        self.output_calls += 1
        output["policy_checked"] = True
        return output


def test_orchestrator_runs_before_output_on_runtime_events() -> None:
    policy = OutputGuardPolicy()
    registry = ToolRegistry()
    orchestrator = Orchestrator(
        runtime_adapter=OpenAIAgentsRuntimeAdapter(),
        policy_middleware=policy,
        tool_executor=DeterministicToolExecutor(registry=registry, policy=policy),
    )
    context = {
        "run_id": "run_output_policy",
        "job_id": "job_output_policy",
        "task_id": "task_output_policy",
        "agent_id": "agent_output_policy",
    }

    import asyncio

    events = asyncio.run(_collect_events(orchestrator, session_id="sess_output_policy", context=context))
    output_events = [event for event in events if event.event_type in {RuntimeEventType.OUTPUT_DELTA, RuntimeEventType.RUN_COMPLETE}]
    assert len(output_events) == 2
    assert policy.output_calls == 2
    for event in output_events:
        assert event.payload["policy_checked"] is True
