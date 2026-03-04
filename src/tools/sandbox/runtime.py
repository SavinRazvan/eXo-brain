"""
File: runtime.py
Path: src/tools/sandbox/runtime.py
Role: Hosted sandbox runtime for tenant tool execution with timeout/resource hooks.
Used By:
 - src/runtime/tenant_runtime.py
Depends On:
 - src/tools/execution_adapter.py
 - src/schemas/tool_io.py
 - src/tools/registry.py
Notes:
 - This runtime is deterministic-envelope compatible and can be feature-flagged.
 - Timeout enforcement is wall-clock based and designed as a first safe baseline.
"""

from __future__ import annotations

from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
from datetime import datetime, timezone
import threading
from time import perf_counter
from typing import Any, Protocol

from src.schemas.tool_io import (
    ExecutionMetadata,
    NormalizedError,
    ToolAudit,
    ToolCallContext,
    ToolExecutionMode,
    ToolResult,
    ToolStatus,
)
from src.tools.execution_adapter import ToolExecutionAdapter
from src.tools.registry import ToolDescriptor
from src.tools.sandbox.policy import SandboxRuntimePolicy
from src.tools.sandbox.pool import TenantSandboxPool
from src.tools.sandbox.process_runner import ProcessRunnerTimeoutError, ProcessSandboxRunner
from src.tools.user_tool_contracts import (
    SANDBOX_CPU_BUDGET_MS_MAX,
    SANDBOX_MEMORY_BUDGET_MB_MAX,
    SandboxLimits,
    parse_sandbox_limits,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class SandboxResourceDecision:
    allow: bool = True
    reason_code: str = "ALLOW"
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


class SandboxResourceHooks(Protocol):
    def before_execute(self, call: ToolCallContext, descriptor: ToolDescriptor) -> SandboxResourceDecision:
        ...

    def after_execute(
        self,
        call: ToolCallContext,
        descriptor: ToolDescriptor,
        duration_ms: int,
    ) -> SandboxResourceDecision:
        ...


class AllowAllSandboxResourceHooks:
    """Default no-op resource hooks for hosted runtime."""

    def before_execute(self, call: ToolCallContext, descriptor: ToolDescriptor) -> SandboxResourceDecision:
        _ = (call, descriptor)
        return SandboxResourceDecision()

    def after_execute(
        self,
        call: ToolCallContext,
        descriptor: ToolDescriptor,
        duration_ms: int,
    ) -> SandboxResourceDecision:
        _ = (call, descriptor, duration_ms)
        return SandboxResourceDecision()


class ManifestBudgetResourceHooks:
    """Enforce per-tool manifest budgets for CPU and memory."""

    def __init__(
        self,
        platform_cpu_budget_ms: int = SANDBOX_CPU_BUDGET_MS_MAX,
        platform_memory_budget_mb: int = SANDBOX_MEMORY_BUDGET_MB_MAX,
    ) -> None:
        self._platform_cpu_budget_ms = platform_cpu_budget_ms
        self._platform_memory_budget_mb = platform_memory_budget_mb

    def before_execute(self, call: ToolCallContext, descriptor: ToolDescriptor) -> SandboxResourceDecision:
        _ = call
        try:
            limits = self._limits_for_descriptor(descriptor)
        except ValueError as exc:
            return SandboxResourceDecision(
                allow=False,
                reason_code="SANDBOX_LIMITS_INVALID",
                message=str(exc),
            )

        if limits.memory_budget_mb is not None and limits.memory_budget_mb > self._platform_memory_budget_mb:
            return SandboxResourceDecision(
                allow=False,
                reason_code="MEMORY_BUDGET_EXCEEDED",
                message=(
                    f"memory_budget_mb={limits.memory_budget_mb} exceeds platform limit "
                    f"{self._platform_memory_budget_mb}."
                ),
                details={"memory_budget_mb": limits.memory_budget_mb},
            )
        if limits.cpu_budget_ms is not None and limits.cpu_budget_ms > self._platform_cpu_budget_ms:
            return SandboxResourceDecision(
                allow=False,
                reason_code="CPU_BUDGET_EXCEEDED",
                message=(
                    f"cpu_budget_ms={limits.cpu_budget_ms} exceeds platform limit "
                    f"{self._platform_cpu_budget_ms}."
                ),
                details={"cpu_budget_ms": limits.cpu_budget_ms},
            )
        return SandboxResourceDecision()

    def after_execute(
        self,
        call: ToolCallContext,
        descriptor: ToolDescriptor,
        duration_ms: int,
    ) -> SandboxResourceDecision:
        _ = call
        try:
            limits = self._limits_for_descriptor(descriptor)
        except ValueError as exc:
            return SandboxResourceDecision(
                allow=False,
                reason_code="SANDBOX_LIMITS_INVALID",
                message=str(exc),
            )

        if limits.cpu_budget_ms is not None and duration_ms > limits.cpu_budget_ms:
            return SandboxResourceDecision(
                allow=False,
                reason_code="CPU_BUDGET_RUNTIME_EXCEEDED",
                message=(
                    f"execution duration {duration_ms}ms exceeded cpu_budget_ms "
                    f"{limits.cpu_budget_ms}."
                ),
                details={"cpu_budget_ms": limits.cpu_budget_ms, "duration_ms": duration_ms},
            )
        return SandboxResourceDecision()

    @staticmethod
    def _limits_for_descriptor(descriptor: ToolDescriptor) -> SandboxLimits:
        return parse_sandbox_limits(descriptor.metadata or {}) or SandboxLimits()


class TenantSandboxToolRuntime(ToolExecutionAdapter):
    """Hosted tenant sandbox execution adapter with timeout/resource checks."""

    def __init__(
        self,
        resource_hooks: SandboxResourceHooks | None = None,
        runtime_pool: TenantSandboxPool | None = None,
        runtime_policy: SandboxRuntimePolicy | None = None,
        process_runner: ProcessSandboxRunner | None = None,
        enable_process_isolation: bool = False,
        min_timeout_ms: int = 100,
        max_timeout_ms: int = 300000,
    ) -> None:
        self._resource_hooks = resource_hooks or ManifestBudgetResourceHooks()
        self._runtime_pool = runtime_pool or TenantSandboxPool(max_workers_per_tenant=1)
        self._runtime_policy = runtime_policy or SandboxRuntimePolicy(
            min_timeout_ms=min_timeout_ms,
            max_timeout_ms=max_timeout_ms,
        )
        self._enable_process_isolation = enable_process_isolation
        self._process_runner = process_runner or ProcessSandboxRunner()
        self._control_lock = threading.Lock()
        self._pending_cancellations: set[str] = set()
        self._cancel_requested_total = 0
        self._cancel_consumed_total = 0
        self._timeout_total = 0

    @property
    def backend_id(self) -> str:
        return "hosted_sandbox_runtime"

    def execute(self, call: ToolCallContext, descriptor: ToolDescriptor) -> ToolResult:
        started = _utc_now()
        started_clock = perf_counter()
        timeout_ms = self._runtime_policy.resolve_timeout_ms(descriptor)
        tenant_id = self._runtime_policy.resolve_tenant_id(call)
        isolation_mode = "process" if self._enable_process_isolation else "thread_pool"

        # Cancellation is currently pre-dispatch only. It is consumed atomically
        # at call start to guarantee one-shot cancel token semantics.
        if self._consume_cancellation(call.call_id):
            return self._cancelled_result(
                call=call,
                started=started,
                started_clock=started_clock,
                timeout_ms=timeout_ms,
                tenant_id=tenant_id,
                isolation_mode=isolation_mode,
                reason_code="CANCEL_TOKEN_PRE_DISPATCH",
            )

        pre_decision = self._resource_hooks.before_execute(call, descriptor)
        if not pre_decision.allow:
            return self._blocked_for_resources(
                call=call,
                started=started,
                started_clock=started_clock,
                timeout_ms=timeout_ms,
                decision=pre_decision,
            )

        try:
            if self._enable_process_isolation:
                raw_output = self._process_runner.run(
                    handler=descriptor.handler,
                    arguments=call.arguments,
                    timeout_ms=timeout_ms,
                )
            else:
                worker = self._runtime_pool.acquire(tenant_id)
                future = worker.executor.submit(self._invoke_handler, descriptor.handler, call.arguments)
                raw_output = future.result(timeout=max(timeout_ms, 1) / 1000.0)

            duration_ms = int((perf_counter() - started_clock) * 1000)
            post_decision = self._resource_hooks.after_execute(call, descriptor, duration_ms)
            if not post_decision.allow:
                return self._blocked_for_resources(
                    call=call,
                    started=started,
                    started_clock=started_clock,
                    timeout_ms=timeout_ms,
                    decision=post_decision,
                )

            return ToolResult(
                schema_version="1.0",
                call_id=call.call_id,
                tool_name=call.tool_name,
                status=ToolStatus.SUCCESS,
                result={
                    "value": self._normalize_output(raw_output),
                    "runtime": {
                        "backend_id": self.backend_id,
                        "timeout_ms": timeout_ms,
                        "tenant_id": tenant_id,
                        "isolation_mode": isolation_mode,
                    },
                },
                execution=ExecutionMetadata(
                    mode_used=ToolExecutionMode.DETERMINISTIC,
                    started_at_utc=started,
                    finished_at_utc=_utc_now(),
                    duration_ms=duration_ms,
                    timeout_ms=timeout_ms,
                ),
                audit=ToolAudit(correlation_id=call.call_id),
            )
        except ProcessRunnerTimeoutError:
            self._record_timeout()
            return ToolResult(
                schema_version="1.0",
                call_id=call.call_id,
                tool_name=call.tool_name,
                status=ToolStatus.TIMEOUT,
                error=NormalizedError(
                    code="HOSTED_RUNTIME_TIMEOUT",
                    category="tool_runtime",
                    message=f"Hosted runtime timed out after {timeout_ms}ms.",
                    retryable=True,
                    details={
                        "backend_id": self.backend_id,
                        "timeout_ms": timeout_ms,
                        "tenant_id": tenant_id,
                        "isolation_mode": "process",
                    },
                ),
                execution=ExecutionMetadata(
                    mode_used=ToolExecutionMode.DETERMINISTIC,
                    started_at_utc=started,
                    finished_at_utc=_utc_now(),
                    duration_ms=int((perf_counter() - started_clock) * 1000),
                    timeout_ms=timeout_ms,
                ),
                audit=ToolAudit(correlation_id=call.call_id),
            )
        except FutureTimeoutError:
            if "future" in locals():
                future.cancel()
            self._record_timeout()
            return ToolResult(
                schema_version="1.0",
                call_id=call.call_id,
                tool_name=call.tool_name,
                status=ToolStatus.TIMEOUT,
                error=NormalizedError(
                    code="HOSTED_RUNTIME_TIMEOUT",
                    category="tool_runtime",
                    message=f"Hosted runtime timed out after {timeout_ms}ms.",
                    retryable=True,
                    details={"backend_id": self.backend_id, "timeout_ms": timeout_ms, "tenant_id": tenant_id},
                ),
                execution=ExecutionMetadata(
                    mode_used=ToolExecutionMode.DETERMINISTIC,
                    started_at_utc=started,
                    finished_at_utc=_utc_now(),
                    duration_ms=int((perf_counter() - started_clock) * 1000),
                    timeout_ms=timeout_ms,
                ),
                audit=ToolAudit(correlation_id=call.call_id),
            )
        except Exception as exc:  # pragma: no cover - defensive runtime boundary
            return ToolResult(
                schema_version="1.0",
                call_id=call.call_id,
                tool_name=call.tool_name,
                status=ToolStatus.ERROR,
                error=NormalizedError(
                    code="HOSTED_RUNTIME_EXECUTION_ERROR",
                    category="tool_runtime",
                    message=str(exc),
                    retryable=False,
                    details={"backend_id": self.backend_id, "tenant_id": tenant_id},
                ),
                execution=ExecutionMetadata(
                    mode_used=ToolExecutionMode.DETERMINISTIC,
                    started_at_utc=started,
                    finished_at_utc=_utc_now(),
                    duration_ms=int((perf_counter() - started_clock) * 1000),
                    timeout_ms=timeout_ms,
                ),
                audit=ToolAudit(correlation_id=call.call_id),
            )

    @staticmethod
    def _invoke_handler(handler, arguments: dict[str, Any]) -> Any:
        return handler(**arguments)

    @staticmethod
    def _normalize_output(raw_output: Any) -> Any:
        model_dump = getattr(raw_output, "model_dump", None)
        if callable(model_dump):
            dumped = model_dump()
            if isinstance(dumped, dict):
                return dumped
        if isinstance(raw_output, dict):
            return raw_output
        return {"value": raw_output}

    def _blocked_for_resources(
        self,
        call: ToolCallContext,
        started: str,
        started_clock: float,
        timeout_ms: int,
        decision: SandboxResourceDecision,
    ) -> ToolResult:
        return ToolResult(
            schema_version="1.0",
            call_id=call.call_id,
            tool_name=call.tool_name,
            status=ToolStatus.BLOCKED,
            error=NormalizedError(
                code="HOSTED_RUNTIME_RESOURCE_BLOCKED",
                category="tool_runtime",
                message=decision.message or "Hosted runtime resource hooks blocked execution.",
                retryable=False,
                details={
                    "backend_id": self.backend_id,
                    "reason_code": decision.reason_code,
                    "tenant_id": self._runtime_policy.resolve_tenant_id(call),
                    **decision.details,
                },
            ),
            execution=ExecutionMetadata(
                mode_used=ToolExecutionMode.DETERMINISTIC,
                started_at_utc=started,
                finished_at_utc=_utc_now(),
                duration_ms=int((perf_counter() - started_clock) * 1000),
                timeout_ms=timeout_ms,
            ),
            audit=ToolAudit(correlation_id=call.call_id),
        )

    def evict_tenant(self, tenant_id: str) -> bool:
        """Evict one tenant worker from the runtime pool."""
        return self._runtime_pool.evict_tenant(tenant_id)

    def pool_stats(self) -> dict[str, int]:
        """Expose pool stats for diagnostics and tests."""
        return self._runtime_pool.stats()

    def evict_idle_tenants(self, max_idle_seconds: float) -> list[str]:
        """Evict idle tenant workers and return evicted tenant IDs."""
        return self._runtime_pool.evict_idle(max_idle_seconds)

    def request_cancellation(self, call_id: str) -> bool:
        """Register a cancel token for a call id (best-effort pre-dispatch)."""
        normalized = str(call_id).strip()
        if not normalized:
            return False
        with self._control_lock:
            if normalized in self._pending_cancellations:
                return False
            self._pending_cancellations.add(normalized)
            self._cancel_requested_total += 1
            return True

    def clear_cancellation(self, call_id: str) -> bool:
        """Clear a previously registered cancel token."""
        normalized = str(call_id).strip()
        if not normalized:
            return False
        with self._control_lock:
            if normalized not in self._pending_cancellations:
                return False
            self._pending_cancellations.remove(normalized)
            return True

    def control_stats(self) -> dict[str, int]:
        """Expose runtime control/cleanup counters for observability."""
        with self._control_lock:
            return {
                "cancel_requested_total": self._cancel_requested_total,
                "cancel_consumed_total": self._cancel_consumed_total,
                "timeout_total": self._timeout_total,
                "pending_cancellations": len(self._pending_cancellations),
            }

    def cleanup_events(self, limit: int = 20) -> list[dict[str, str]]:
        """Expose recent worker cleanup events emitted by the runtime pool."""
        return self._runtime_pool.cleanup_events(limit=limit)

    def _consume_cancellation(self, call_id: str) -> bool:
        normalized = str(call_id).strip()
        if not normalized:
            return False
        with self._control_lock:
            if normalized not in self._pending_cancellations:
                return False
            self._pending_cancellations.remove(normalized)
            self._cancel_consumed_total += 1
            return True

    def _record_timeout(self) -> None:
        with self._control_lock:
            self._timeout_total += 1

    def _cancelled_result(
        self,
        call: ToolCallContext,
        started: str,
        started_clock: float,
        timeout_ms: int,
        tenant_id: str,
        isolation_mode: str,
        reason_code: str,
    ) -> ToolResult:
        return ToolResult(
            schema_version="1.0",
            call_id=call.call_id,
            tool_name=call.tool_name,
            status=ToolStatus.CANCELLED,
            error=NormalizedError(
                code="HOSTED_RUNTIME_CANCELLED",
                category="tool_runtime",
                message="Hosted runtime call cancelled before execution dispatch.",
                retryable=True,
                details={
                    "backend_id": self.backend_id,
                    "tenant_id": tenant_id,
                    "isolation_mode": isolation_mode,
                    "reason_code": reason_code,
                },
            ),
            execution=ExecutionMetadata(
                mode_used=ToolExecutionMode.DETERMINISTIC,
                started_at_utc=started,
                finished_at_utc=_utc_now(),
                duration_ms=int((perf_counter() - started_clock) * 1000),
                timeout_ms=timeout_ms,
            ),
            audit=ToolAudit(correlation_id=call.call_id),
        )
