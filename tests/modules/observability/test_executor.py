"""
File: test_executor.py
Path: tests/modules/observability/test_executor.py
Role: Unit tests for deterministic tool executor success and failure envelopes.
Used By:
 - pytest
Depends On:
 - src/tools/executor.py
 - src/tools/registry.py
 - src/policies/middleware.py
 - src/schemas/tool_io.py
Notes:
 - Ensures unknown tools and successful calls produce normalized results.
"""

from src.policies.middleware import DeterministicFirstPolicyMiddleware
from src.observability.metrics import RuntimeMetrics
from src.schemas.tool_io import RiskTier, ToolCallContext, ToolStatus
from src.tools.executor import DeterministicToolExecutor
from src.tools.registry import ToolDescriptor, ToolRegistry


def test_executor_success_path() -> None:
    registry = ToolRegistry()
    registry.register(
        ToolDescriptor(
            name="sum_tool",
            handler=lambda a, b: a + b,
            risk_tier=RiskTier.LOW,
        )
    )
    executor = DeterministicToolExecutor(registry=registry, policy=DeterministicFirstPolicyMiddleware())
    call = ToolCallContext(
        schema_version="1.0",
        call_id="tc_ok",
        session_id="sess_1",
        run_id="run_1",
        job_id="job_1",
        task_id="task_1",
        agent_id="agent_1",
        provider_id="openai",
        tool_name="sum_tool",
        arguments={"a": 2, "b": 3},
    )
    result = executor.execute(call)
    assert result.status == ToolStatus.SUCCESS
    assert result.result == {"value": 5}


def test_executor_unknown_tool_returns_error_envelope() -> None:
    executor = DeterministicToolExecutor(registry=ToolRegistry(), policy=DeterministicFirstPolicyMiddleware())
    call = ToolCallContext(
        schema_version="1.0",
        call_id="tc_missing",
        session_id="sess_1",
        run_id="run_1",
        job_id="job_1",
        task_id="task_1",
        agent_id="agent_1",
        provider_id="openai",
        tool_name="missing_tool",
        arguments={},
    )
    result = executor.execute(call)
    assert result.status == ToolStatus.ERROR
    assert result.error.code == "TOOL_NOT_FOUND"


def test_executor_updates_metrics_for_success_and_failure() -> None:
    registry = ToolRegistry()
    registry.register(ToolDescriptor(name="ok_tool", handler=lambda: "ok", risk_tier=RiskTier.LOW))
    metrics = RuntimeMetrics()
    executor = DeterministicToolExecutor(
        registry=registry,
        policy=DeterministicFirstPolicyMiddleware(),
        metrics=metrics,
    )

    ok_call = ToolCallContext(
        schema_version="1.0",
        call_id="tc_ok_metrics",
        session_id="sess_1",
        run_id="run_1",
        job_id="job_1",
        task_id="task_1",
        agent_id="agent_1",
        provider_id="openai",
        tool_name="ok_tool",
        arguments={},
    )
    missing_call = ToolCallContext(
        schema_version="1.0",
        call_id="tc_missing_metrics",
        session_id="sess_1",
        run_id="run_1",
        job_id="job_1",
        task_id="task_1",
        agent_id="agent_1",
        provider_id="openai",
        tool_name="missing_tool",
        arguments={},
    )

    assert executor.execute(ok_call).status == ToolStatus.SUCCESS
    assert executor.execute(missing_call).status == ToolStatus.ERROR

    assert metrics.counters["tool.call.total"] == 2
    assert metrics.counters["tool.call.success"] == 1
    assert metrics.counters["tool.call.failed"] == 1
