"""
File: test_sandbox_runtime.py
Path: tests/modules/tools/test_sandbox_runtime.py
Role: Unit tests for hosted sandbox runtime timeout/resource/result mapping behavior.
Used By:
 - pytest
Depends On:
 - src/tools/sandbox/runtime.py
 - src/schemas/tool_io.py
 - src/tools/registry.py
Notes:
 - Covers success, timeout, handler error, and resource-hook blocking paths.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os
import time

from src.schemas.tool_io import ToolCallContext, ToolStatus
from src.tools.registry import ToolDescriptor
from src.tools.sandbox.pool import TenantSandboxPool
from src.tools.sandbox.runtime import (
    SandboxResourceDecision,
    TenantSandboxToolRuntime,
)


def _process_add(a: int, b: int) -> int:
    return a + b


def _process_slow() -> str:
    time.sleep(0.05)
    return "late"


def _sleep_and_echo(value: str, delay_ms: int = 10) -> dict[str, str]:
    time.sleep(max(delay_ms, 0) / 1000.0)
    return {"value": value}


def _sleep_only(delay_ms: int = 50) -> str:
    time.sleep(max(delay_ms, 0) / 1000.0)
    return "done"


def _process_crash() -> None:
    os._exit(13)


def _call(tool_name: str = "math_tool", arguments: dict | None = None) -> ToolCallContext:
    return ToolCallContext(
        schema_version="1.0",
        call_id="tc_sandbox",
        session_id="sess_1",
        run_id="run_1",
        job_id="job_1",
        task_id="task_1",
        agent_id="agent_1",
        provider_id="openai",
        tool_name=tool_name,
        arguments=arguments or {},
    )


def _tenant_call(tenant_id: str, tool_name: str = "math_tool", arguments: dict | None = None) -> ToolCallContext:
    call = _call(tool_name=tool_name, arguments=arguments)
    call.tenant_id = tenant_id
    return call


def test_hosted_runtime_executes_successfully_and_maps_result() -> None:
    runtime = TenantSandboxToolRuntime()
    descriptor = ToolDescriptor(name="math_tool", handler=lambda a, b: a + b, timeout_ms=1000)
    result = runtime.execute(_call(arguments={"a": 2, "b": 3}), descriptor)
    assert result.status == ToolStatus.SUCCESS
    assert result.result is not None
    assert result.result["value"] == {"value": 5}
    assert result.result["runtime"]["backend_id"] == "hosted_sandbox_runtime"
    assert result.result["runtime"]["isolation_mode"] == "thread_pool"


def test_hosted_runtime_returns_timeout_envelope() -> None:
    runtime = TenantSandboxToolRuntime(min_timeout_ms=1)

    def _slow() -> str:
        time.sleep(0.05)
        return "late"

    descriptor = ToolDescriptor(name="math_tool", handler=_slow, timeout_ms=10)
    result = runtime.execute(_call(), descriptor)
    assert result.status == ToolStatus.TIMEOUT
    assert result.error.code == "HOSTED_RUNTIME_TIMEOUT"


def test_hosted_runtime_returns_error_envelope_on_handler_failure() -> None:
    runtime = TenantSandboxToolRuntime()

    def _boom() -> None:
        raise ValueError("bad input")

    descriptor = ToolDescriptor(name="math_tool", handler=_boom, timeout_ms=1000)
    result = runtime.execute(_call(), descriptor)
    assert result.status == ToolStatus.ERROR
    assert result.error.code == "HOSTED_RUNTIME_EXECUTION_ERROR"


def test_hosted_runtime_blocks_execution_when_resource_hook_denies_before() -> None:
    class _DenyPreHook:
        def before_execute(self, call: ToolCallContext, descriptor: ToolDescriptor) -> SandboxResourceDecision:
            _ = (call, descriptor)
            return SandboxResourceDecision(
                allow=False,
                reason_code="MEMORY_LIMIT",
                message="memory quota exceeded",
                details={"max_memory_mb": 128},
            )

        def after_execute(
            self,
            call: ToolCallContext,
            descriptor: ToolDescriptor,
            duration_ms: int,
        ) -> SandboxResourceDecision:
            _ = (call, descriptor, duration_ms)
            return SandboxResourceDecision()

    runtime = TenantSandboxToolRuntime(resource_hooks=_DenyPreHook())
    descriptor = ToolDescriptor(name="math_tool", handler=lambda: "ok", timeout_ms=1000)
    result = runtime.execute(_call(), descriptor)
    assert result.status == ToolStatus.BLOCKED
    assert result.error.code == "HOSTED_RUNTIME_RESOURCE_BLOCKED"
    assert result.error.details["reason_code"] == "MEMORY_LIMIT"


def test_hosted_runtime_blocks_when_manifest_memory_budget_exceeds_platform_limit() -> None:
    from src.tools.sandbox.runtime import ManifestBudgetResourceHooks

    runtime = TenantSandboxToolRuntime(
        resource_hooks=ManifestBudgetResourceHooks(platform_memory_budget_mb=256),
    )
    descriptor = ToolDescriptor(
        name="math_tool",
        handler=lambda: "ok",
        timeout_ms=1000,
        metadata={"sandbox_limits": {"memory_budget_mb": 512}},
    )
    result = runtime.execute(_call(), descriptor)
    assert result.status == ToolStatus.BLOCKED
    assert result.error.code == "HOSTED_RUNTIME_RESOURCE_BLOCKED"
    assert result.error.details["reason_code"] == "MEMORY_BUDGET_EXCEEDED"


def test_hosted_runtime_blocks_when_manifest_cpu_budget_runtime_exceeded() -> None:
    runtime = TenantSandboxToolRuntime(min_timeout_ms=1)

    def _slow() -> str:
        time.sleep(0.03)
        return "ok"

    descriptor = ToolDescriptor(
        name="math_tool",
        handler=_slow,
        timeout_ms=1000,
        metadata={"sandbox_limits": {"cpu_budget_ms": 10}},
    )
    result = runtime.execute(_call(), descriptor)
    assert result.status == ToolStatus.BLOCKED
    assert result.error.code == "HOSTED_RUNTIME_RESOURCE_BLOCKED"
    assert result.error.details["reason_code"] == "CPU_BUDGET_RUNTIME_EXCEEDED"


def test_hosted_runtime_pool_creates_workers_per_tenant_and_evicts() -> None:
    pool = TenantSandboxPool(max_workers_per_tenant=1)
    runtime = TenantSandboxToolRuntime(runtime_pool=pool)
    descriptor = ToolDescriptor(name="math_tool", handler=lambda: "ok", timeout_ms=1000)

    assert runtime.execute(_tenant_call("t1"), descriptor).status == ToolStatus.SUCCESS
    assert runtime.execute(_tenant_call("t2"), descriptor).status == ToolStatus.SUCCESS
    assert runtime.pool_stats()["tenants"] == 2

    assert runtime.evict_tenant("t1") is True
    assert runtime.pool_stats()["tenants"] == 1
    assert runtime.execute(_tenant_call("t1"), descriptor).status == ToolStatus.SUCCESS
    assert runtime.pool_stats()["tenants"] == 2
    pool.close()


def test_hosted_runtime_exposes_idle_eviction() -> None:
    now = {"value": 0.0}

    def _clock() -> float:
        return now["value"]

    pool = TenantSandboxPool(max_workers_per_tenant=1, clock=_clock)
    runtime = TenantSandboxToolRuntime(runtime_pool=pool)
    descriptor = ToolDescriptor(name="math_tool", handler=lambda: "ok", timeout_ms=1000)

    assert runtime.execute(_tenant_call("t1"), descriptor).status == ToolStatus.SUCCESS
    now["value"] = 10.0
    assert runtime.execute(_tenant_call("t2"), descriptor).status == ToolStatus.SUCCESS
    evicted = runtime.evict_idle_tenants(max_idle_seconds=5.0)
    assert evicted == ["t1"]
    assert runtime.pool_stats()["tenants"] == 1
    pool.close()


def test_hosted_runtime_process_isolation_executes_successfully() -> None:
    runtime = TenantSandboxToolRuntime(enable_process_isolation=True)
    descriptor = ToolDescriptor(name="math_tool", handler=_process_add, timeout_ms=1000)
    result = runtime.execute(_call(arguments={"a": 4, "b": 8}), descriptor)
    assert result.status == ToolStatus.SUCCESS
    assert result.result is not None
    assert result.result["value"] == {"value": 12}
    assert result.result["runtime"]["isolation_mode"] == "process"


def test_hosted_runtime_process_isolation_returns_timeout_envelope() -> None:
    runtime = TenantSandboxToolRuntime(enable_process_isolation=True, min_timeout_ms=1)
    descriptor = ToolDescriptor(name="math_tool", handler=_process_slow, timeout_ms=10)
    result = runtime.execute(_call(), descriptor)
    assert result.status == ToolStatus.TIMEOUT
    assert result.error.code == "HOSTED_RUNTIME_TIMEOUT"
    assert result.error.details["isolation_mode"] == "process"


def test_hosted_runtime_thread_pool_concurrency_isolates_tenants_under_load() -> None:
    runtime = TenantSandboxToolRuntime(
        runtime_pool=TenantSandboxPool(max_workers_per_tenant=1, max_tenants=64),
    )
    descriptor = ToolDescriptor(name="math_tool", handler=_sleep_and_echo, timeout_ms=500)
    tenant_ids = [f"tenant-{idx}" for idx in range(24)]

    def _invoke(tenant_id: str) -> tuple[str, ToolStatus, dict | None]:
        call = _tenant_call(tenant_id, arguments={"value": tenant_id, "delay_ms": 20})
        result = runtime.execute(call, descriptor)
        return tenant_id, result.status, result.result

    with ThreadPoolExecutor(max_workers=24) as executor:
        responses = list(executor.map(_invoke, tenant_ids))

    assert len(responses) == len(tenant_ids)
    for tenant_id, status, result in responses:
        assert status == ToolStatus.SUCCESS
        assert result is not None
        assert result["value"] == {"value": tenant_id}
        assert result["runtime"]["tenant_id"] == tenant_id
        assert result["runtime"]["isolation_mode"] == "thread_pool"

    # Per-tenant worker state should be present for all active tenants in this run.
    assert runtime.pool_stats()["tenants"] == len(tenant_ids)


def test_hosted_runtime_concurrency_mixed_long_running_timeouts_do_not_break_fast_tenants() -> None:
    runtime = TenantSandboxToolRuntime(min_timeout_ms=1)
    fast_descriptor = ToolDescriptor(name="math_tool", handler=_sleep_and_echo, timeout_ms=200)
    slow_descriptor = ToolDescriptor(name="math_tool", handler=_sleep_only, timeout_ms=15)
    fast_tenants = [f"fast-{idx}" for idx in range(8)]
    slow_tenants = [f"slow-{idx}" for idx in range(8)]

    def _invoke_fast(tenant_id: str) -> ToolStatus:
        call = _tenant_call(tenant_id, arguments={"value": tenant_id, "delay_ms": 5})
        return runtime.execute(call, fast_descriptor).status

    def _invoke_slow(tenant_id: str) -> ToolStatus:
        call = _tenant_call(tenant_id, arguments={"delay_ms": 60})
        return runtime.execute(call, slow_descriptor).status

    with ThreadPoolExecutor(max_workers=16) as executor:
        fast_futures = [executor.submit(_invoke_fast, tenant_id) for tenant_id in fast_tenants]
        slow_futures = [executor.submit(_invoke_slow, tenant_id) for tenant_id in slow_tenants]

    fast_statuses = [future.result() for future in fast_futures]
    slow_statuses = [future.result() for future in slow_futures]

    assert all(status == ToolStatus.SUCCESS for status in fast_statuses)
    assert all(status == ToolStatus.TIMEOUT for status in slow_statuses)


def test_hosted_runtime_process_isolation_concurrency_handles_many_tenants() -> None:
    runtime = TenantSandboxToolRuntime(enable_process_isolation=True, min_timeout_ms=1)
    descriptor = ToolDescriptor(name="math_tool", handler=_sleep_and_echo, timeout_ms=3000)
    tenant_ids = [f"proc-{idx}" for idx in range(8)]

    def _invoke(tenant_id: str) -> ToolStatus:
        call = _tenant_call(tenant_id, arguments={"value": tenant_id, "delay_ms": 10})
        result = runtime.execute(call, descriptor)
        assert result.result is not None
        assert result.result["runtime"]["tenant_id"] == tenant_id
        assert result.result["runtime"]["isolation_mode"] == "process"
        return result.status

    with ThreadPoolExecutor(max_workers=8) as executor:
        statuses = list(executor.map(_invoke, tenant_ids))

    assert all(status == ToolStatus.SUCCESS for status in statuses)


def test_hosted_runtime_process_isolation_concurrency_times_out_long_running_handlers() -> None:
    runtime = TenantSandboxToolRuntime(enable_process_isolation=True, min_timeout_ms=1)
    descriptor = ToolDescriptor(name="math_tool", handler=_sleep_only, timeout_ms=10)
    tenant_ids = [f"proc-timeout-{idx}" for idx in range(6)]

    def _invoke(tenant_id: str) -> ToolStatus:
        call = _tenant_call(tenant_id, arguments={"delay_ms": 60})
        result = runtime.execute(call, descriptor)
        assert result.error is not None
        assert result.error.code == "HOSTED_RUNTIME_TIMEOUT"
        assert result.error.details["isolation_mode"] == "process"
        assert result.error.details["tenant_id"] == tenant_id
        return result.status

    with ThreadPoolExecutor(max_workers=6) as executor:
        statuses = list(executor.map(_invoke, tenant_ids))

    assert all(status == ToolStatus.TIMEOUT for status in statuses)


def test_hosted_runtime_cancel_token_returns_cancelled_before_dispatch() -> None:
    calls = {"count": 0}

    def _handler() -> str:
        calls["count"] += 1
        return "ok"

    runtime = TenantSandboxToolRuntime()
    descriptor = ToolDescriptor(name="math_tool", handler=_handler, timeout_ms=500)
    call = _call()
    assert runtime.request_cancellation(call.call_id) is True
    result = runtime.execute(call, descriptor)
    assert result.status == ToolStatus.CANCELLED
    assert result.error.code == "HOSTED_RUNTIME_CANCELLED"
    assert result.error.details["reason_code"] == "CANCEL_TOKEN_PRE_DISPATCH"
    assert calls["count"] == 0
    control_stats = runtime.control_stats()
    assert control_stats["cancel_requested_total"] == 1
    assert control_stats["cancel_consumed_total"] == 1
    assert control_stats["pending_cancellations"] == 0


def test_hosted_runtime_thread_timeout_recovers_on_next_call_same_tenant() -> None:
    runtime = TenantSandboxToolRuntime(min_timeout_ms=1)
    timeout_descriptor = ToolDescriptor(name="math_tool", handler=_sleep_only, timeout_ms=10)
    ok_descriptor = ToolDescriptor(name="math_tool", handler=lambda: "ok", timeout_ms=500)
    timeout_result = runtime.execute(_tenant_call("recover-thread", arguments={"delay_ms": 60}), timeout_descriptor)
    assert timeout_result.status == ToolStatus.TIMEOUT
    ok_result = runtime.execute(_tenant_call("recover-thread"), ok_descriptor)
    assert ok_result.status == ToolStatus.SUCCESS
    assert runtime.control_stats()["timeout_total"] >= 1


def test_hosted_runtime_process_crash_recovers_on_next_call() -> None:
    runtime = TenantSandboxToolRuntime(enable_process_isolation=True)
    crash_descriptor = ToolDescriptor(name="math_tool", handler=_process_crash, timeout_ms=500)
    ok_descriptor = ToolDescriptor(name="math_tool", handler=_process_add, timeout_ms=500)

    crash = runtime.execute(_tenant_call("recover-process"), crash_descriptor)
    assert crash.status == ToolStatus.ERROR
    assert crash.error.code == "HOSTED_RUNTIME_EXECUTION_ERROR"

    ok = runtime.execute(_tenant_call("recover-process", arguments={"a": 2, "b": 5}), ok_descriptor)
    assert ok.status == ToolStatus.SUCCESS
    assert ok.result is not None
    assert ok.result["value"] == {"value": 7}


def test_hosted_runtime_cleanup_observability_reports_idle_evictions() -> None:
    now = {"value": 0.0}

    def _clock() -> float:
        return now["value"]

    pool = TenantSandboxPool(max_workers_per_tenant=1, clock=_clock)
    runtime = TenantSandboxToolRuntime(runtime_pool=pool)
    descriptor = ToolDescriptor(name="math_tool", handler=lambda: "ok", timeout_ms=1000)
    assert runtime.execute(_tenant_call("cleanup-t1"), descriptor).status == ToolStatus.SUCCESS
    now["value"] = 10.0
    assert runtime.execute(_tenant_call("cleanup-t2"), descriptor).status == ToolStatus.SUCCESS
    assert runtime.evict_idle_tenants(max_idle_seconds=5.0) == ["cleanup-t1"]
    stats = runtime.pool_stats()
    assert stats["evicted_workers_idle"] == 1
    events = runtime.cleanup_events(limit=5)
    assert events[-1]["tenant_id"] == "cleanup-t1"
    assert events[-1]["reason"] == "idle_ttl"
    pool.close()
