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
from src.schemas.tool_io import (
    ExecutionMetadata,
    RiskTier,
    ToolAudit,
    ToolCallContext,
    ToolExecutionMode,
    ToolResult,
    ToolStatus,
)
from src.tools.execution_adapter import ToolExecutionAdapter
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


def test_executor_rejects_invalid_call_payload_shape() -> None:
    registry = ToolRegistry()
    registry.register(ToolDescriptor(name="ok_tool", handler=lambda: "ok", risk_tier=RiskTier.LOW))
    executor = DeterministicToolExecutor(registry=registry, policy=DeterministicFirstPolicyMiddleware())
    bad_call = ToolCallContext(
        schema_version="1.0",
        call_id="tc_bad_args",
        session_id="sess_1",
        run_id="run_1",
        job_id="job_1",
        task_id="task_1",
        agent_id="agent_1",
        provider_id="openai",
        tool_name="ok_tool",
        arguments="not-an-object",  # type: ignore[arg-type]
    )
    result = executor.execute(bad_call)
    assert result.status == ToolStatus.ERROR
    assert result.error.code == "TOOL_CALL_VALIDATION_ERROR"


def test_executor_rejects_unsupported_schema_version() -> None:
    registry = ToolRegistry()
    registry.register(ToolDescriptor(name="ok_tool", handler=lambda: "ok", risk_tier=RiskTier.LOW))
    executor = DeterministicToolExecutor(registry=registry, policy=DeterministicFirstPolicyMiddleware())
    bad_call = ToolCallContext(
        schema_version="2.0",
        call_id="tc_bad_schema",
        session_id="sess_1",
        run_id="run_1",
        job_id="job_1",
        task_id="task_1",
        agent_id="agent_1",
        provider_id="openai",
        tool_name="ok_tool",
        arguments={},
    )
    result = executor.execute(bad_call)
    assert result.status == ToolStatus.ERROR
    assert result.error.code == "TOOL_CALL_VALIDATION_ERROR"


class _RecordingAdapter(ToolExecutionAdapter):
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    @property
    def backend_id(self) -> str:
        return "recording_adapter"

    def execute(self, call: ToolCallContext, descriptor: ToolDescriptor) -> ToolResult:
        self.calls.append((call.tool_name, descriptor.name))
        return ToolResult(
            schema_version="1.0",
            call_id=call.call_id,
            tool_name=call.tool_name,
            status=ToolStatus.SUCCESS,
            result={"value": {"backend": self.backend_id}},
            execution=ExecutionMetadata(mode_used=ToolExecutionMode.DETERMINISTIC),
            audit=ToolAudit(correlation_id=call.call_id),
        )


def test_executor_default_path_does_not_delegate_without_flag() -> None:
    registry = ToolRegistry()
    registry.register(ToolDescriptor(name="sum_tool", handler=lambda a, b: a + b, risk_tier=RiskTier.LOW))
    adapter = _RecordingAdapter()
    executor = DeterministicToolExecutor(
        registry=registry,
        policy=DeterministicFirstPolicyMiddleware(),
        execution_adapter=adapter,
        enable_hosted_runtime=False,
    )
    call = ToolCallContext(
        schema_version="1.0",
        call_id="tc_local_path",
        session_id="sess_1",
        run_id="run_1",
        job_id="job_1",
        task_id="task_1",
        agent_id="agent_1",
        provider_id="openai",
        tool_name="sum_tool",
        arguments={"a": 1, "b": 2},
    )
    result = executor.execute(call)
    assert result.status == ToolStatus.SUCCESS
    assert result.result == {"value": 3}
    assert adapter.calls == []


def test_executor_delegates_to_adapter_when_flag_enabled() -> None:
    registry = ToolRegistry()
    registry.register(ToolDescriptor(name="sum_tool", handler=lambda a, b: a + b, risk_tier=RiskTier.LOW))
    adapter = _RecordingAdapter()
    executor = DeterministicToolExecutor(
        registry=registry,
        policy=DeterministicFirstPolicyMiddleware(),
        execution_adapter=adapter,
        enable_hosted_runtime=True,
    )
    call = ToolCallContext(
        schema_version="1.0",
        call_id="tc_delegated_path",
        session_id="sess_1",
        run_id="run_1",
        job_id="job_1",
        task_id="task_1",
        agent_id="agent_1",
        provider_id="openai",
        tool_name="sum_tool",
        arguments={"a": 1, "b": 2},
    )
    result = executor.execute(call)
    assert result.status == ToolStatus.SUCCESS
    assert result.result == {"value": {"backend": "recording_adapter"}}
    assert adapter.calls == [("sum_tool", "sum_tool")]
