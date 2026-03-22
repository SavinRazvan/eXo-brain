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
from src.policies.risk_gates import RiskGateConfig
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


def test_executor_validation_failure_increments_failed_metric() -> None:
    registry = ToolRegistry()
    registry.register(ToolDescriptor(name="ok_tool", handler=lambda: "ok", risk_tier=RiskTier.LOW))
    metrics = RuntimeMetrics()
    executor = DeterministicToolExecutor(
        registry=registry,
        policy=DeterministicFirstPolicyMiddleware(),
        metrics=metrics,
    )
    bad_call = ToolCallContext(
        schema_version="0.9",
        call_id="tc",
        session_id="sess_1",
        run_id="run_1",
        job_id="job_1",
        task_id="task_1",
        agent_id="agent_1",
        provider_id="openai",
        tool_name="ok_tool",
        arguments={},
    )
    assert executor.execute(bad_call).status == ToolStatus.ERROR
    assert metrics.counters["tool.call.total"] == 1
    assert metrics.counters["tool.call.failed"] == 1


def test_executor_blank_tool_name_is_validation_error() -> None:
    registry = ToolRegistry()
    registry.register(ToolDescriptor(name="ok_tool", handler=lambda: "ok", risk_tier=RiskTier.LOW))
    executor = DeterministicToolExecutor(registry=registry, policy=DeterministicFirstPolicyMiddleware())
    call = ToolCallContext(
        schema_version="1.0",
        call_id="tc",
        session_id="sess_1",
        run_id="run_1",
        job_id="job_1",
        task_id="task_1",
        agent_id="agent_1",
        provider_id="openai",
        tool_name="   ",
        arguments={},
    )
    result = executor.execute(call)
    assert result.status == ToolStatus.ERROR
    assert result.error.code == "TOOL_CALL_VALIDATION_ERROR"


def test_executor_policy_deny_increments_blocked_metric() -> None:
    registry = ToolRegistry()
    registry.register(ToolDescriptor(name="sum_tool", handler=lambda a, b: a + b, risk_tier=RiskTier.LOW))
    policy = DeterministicFirstPolicyMiddleware(risk_gate_config=RiskGateConfig(deny_tools={"sum_tool"}))
    metrics = RuntimeMetrics()
    executor = DeterministicToolExecutor(registry=registry, policy=policy, metrics=metrics)
    call = ToolCallContext(
        schema_version="1.0",
        call_id="tc",
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
    assert result.status == ToolStatus.BLOCKED
    assert metrics.counters["tool.call.blocked"] == 1
    assert metrics.counters.get("tool.call.failed", 0) == 0
    assert metrics.counters.get("tool.call.postcheck_failed", 0) == 0


def test_executor_handler_exception_returns_tool_execution_error() -> None:
    registry = ToolRegistry()
    registry.register(
        ToolDescriptor(name="boom_tool", handler=lambda: (_ for _ in ()).throw(RuntimeError("boom")), risk_tier=RiskTier.LOW)
    )
    metrics = RuntimeMetrics()
    executor = DeterministicToolExecutor(
        registry=registry,
        policy=DeterministicFirstPolicyMiddleware(),
        metrics=metrics,
    )
    call = ToolCallContext(
        schema_version="1.0",
        call_id="tc",
        session_id="sess_1",
        run_id="run_1",
        job_id="job_1",
        task_id="task_1",
        agent_id="agent_1",
        provider_id="openai",
        tool_name="boom_tool",
        arguments={},
    )
    result = executor.execute(call)
    assert result.status == ToolStatus.ERROR
    assert result.error.code == "TOOL_EXECUTION_ERROR"
    assert metrics.counters["tool.call.failed"] == 1


def test_executor_hosted_path_merges_runtime_projection_into_dict_result() -> None:
    registry = ToolRegistry()
    registry.register(
        ToolDescriptor(
            name="echo_tool",
            handler=lambda: None,
            risk_tier=RiskTier.LOW,
            metadata={"tool_version": "9.9.9", "package_ref": "pkg", "handler_ref": "h1"},
        )
    )

    class _DictAdapter(ToolExecutionAdapter):
        @property
        def backend_id(self) -> str:
            return "dict_adapter"

        def execute(self, call: ToolCallContext, descriptor: ToolDescriptor) -> ToolResult:
            return ToolResult(
                schema_version="1.0",
                call_id=call.call_id,
                tool_name=call.tool_name,
                status=ToolStatus.SUCCESS,
                result={"value": {"k": 1}},
                execution=ExecutionMetadata(mode_used=ToolExecutionMode.DETERMINISTIC),
                audit=ToolAudit(correlation_id=call.call_id),
            )

    adapter = _DictAdapter()
    executor = DeterministicToolExecutor(
        registry=registry,
        policy=DeterministicFirstPolicyMiddleware(),
        execution_adapter=adapter,
        enable_hosted_runtime=True,
    )
    call = ToolCallContext(
        schema_version="1.0",
        call_id="tc",
        session_id="sess_1",
        run_id="run_1",
        job_id="job_1",
        task_id="task_1",
        agent_id="agent_1",
        provider_id="openai",
        tool_name="echo_tool",
        arguments={},
    )
    result = executor.execute(call)
    assert result.status == ToolStatus.SUCCESS
    assert result.result["runtime"]["tool_version"] == "9.9.9"
    assert result.result["runtime"]["package_ref"] == "pkg"


def test_executor_hosted_path_postcheck_failure_increments_metrics() -> None:
    registry = ToolRegistry()
    registry.register(ToolDescriptor(name="x", handler=lambda: None, risk_tier=RiskTier.LOW))

    class _BadPostAdapter(ToolExecutionAdapter):
        @property
        def backend_id(self) -> str:
            return "bad"

        def execute(self, call: ToolCallContext, descriptor: ToolDescriptor) -> ToolResult:
            return ToolResult(
                schema_version="1.0",
                call_id=call.call_id,
                tool_name=call.tool_name,
                status=ToolStatus.SUCCESS,
                result=None,
                execution=ExecutionMetadata(mode_used=ToolExecutionMode.DETERMINISTIC),
                audit=ToolAudit(correlation_id=call.call_id),
            )

    metrics = RuntimeMetrics()
    executor = DeterministicToolExecutor(
        registry=registry,
        policy=DeterministicFirstPolicyMiddleware(),
        execution_adapter=_BadPostAdapter(),
        metrics=metrics,
        enable_hosted_runtime=True,
    )
    call = ToolCallContext(
        schema_version="1.0",
        call_id="tc",
        session_id="sess_1",
        run_id="run_1",
        job_id="job_1",
        task_id="task_1",
        agent_id="agent_1",
        provider_id="openai",
        tool_name="x",
        arguments={},
    )
    result = executor.execute(call)
    assert result.status == ToolStatus.ERROR
    assert metrics.counters["tool.call.postcheck_failed"] == 1
    assert metrics.counters["tool.call.failed"] == 1


def test_executor_local_handler_postcheck_failure_increments_metrics() -> None:
    registry = ToolRegistry()
    registry.register(ToolDescriptor(name="noop", handler=lambda: None, risk_tier=RiskTier.LOW))
    metrics = RuntimeMetrics()

    class _PostFailPolicy(DeterministicFirstPolicyMiddleware):
        def after_tool_call(self, result: ToolResult) -> ToolResult:
            if result.tool_name == "noop" and result.status == ToolStatus.SUCCESS:
                return ToolResult(
                    schema_version=result.schema_version,
                    call_id=result.call_id,
                    tool_name=result.tool_name,
                    status=ToolStatus.ERROR,
                    error=result.error,
                    execution=result.execution,
                    audit=result.audit,
                )
            return super().after_tool_call(result)

    executor = DeterministicToolExecutor(
        registry=registry,
        policy=_PostFailPolicy(),
        metrics=metrics,
    )
    call = ToolCallContext(
        schema_version="1.0",
        call_id="tc",
        session_id="sess_1",
        run_id="run_1",
        job_id="job_1",
        task_id="task_1",
        agent_id="agent_1",
        provider_id="openai",
        tool_name="noop",
        arguments={},
    )
    result = executor.execute(call)
    assert result.status == ToolStatus.ERROR
    assert metrics.counters["tool.call.postcheck_failed"] == 1


def test_executor_execution_adapter_accessor_respects_flag() -> None:
    registry = ToolRegistry()
    adapter = _RecordingAdapter()
    off = DeterministicToolExecutor(
        registry=registry,
        policy=DeterministicFirstPolicyMiddleware(),
        execution_adapter=adapter,
        enable_hosted_runtime=False,
    )
    assert off.execution_adapter() is None
    on = DeterministicToolExecutor(
        registry=registry,
        policy=DeterministicFirstPolicyMiddleware(),
        execution_adapter=adapter,
        enable_hosted_runtime=True,
    )
    assert on.execution_adapter() is adapter


def test_executor_success_includes_runtime_projection_from_metadata() -> None:
    registry = ToolRegistry()
    registry.register(
        ToolDescriptor(
            name="meta_tool",
            handler=lambda: 1,
            risk_tier=RiskTier.LOW,
            metadata={"tool_version": "1.2.3"},
        )
    )
    executor = DeterministicToolExecutor(registry=registry, policy=DeterministicFirstPolicyMiddleware())
    call = ToolCallContext(
        schema_version="1.0",
        call_id="tc",
        session_id="sess_1",
        run_id="run_1",
        job_id="job_1",
        task_id="task_1",
        agent_id="agent_1",
        provider_id="openai",
        tool_name="meta_tool",
        arguments={},
    )
    result = executor.execute(call)
    assert result.result["runtime"]["tool_version"] == "1.2.3"
