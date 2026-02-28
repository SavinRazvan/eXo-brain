"""
File: executor.py
Path: src/tools/executor.py
Role: Deterministic tool execution runtime with policy-gated envelopes.
Used By:
 - src/core/orchestrator.py
Depends On:
 - src/tools/registry.py
 - src/policies/middleware.py
 - src/schemas/tool_io.py
Notes:
 - All side-effecting operations should route through this executor.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.policies.middleware import PolicyMiddleware
from src.observability.metrics import RuntimeMetrics
from src.schemas.tool_io import (
    ExecutionMetadata,
    NormalizedError,
    PolicyAction,
    ToolAudit,
    ToolCallContext,
    ToolExecutionMode,
    ToolResult,
    ToolStatus,
    blocked_result,
)
from src.tools.registry import ToolRegistry
from src.tools.decorators import AuditSink, apply_execution_decorators


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DeterministicToolExecutor:
    def __init__(
        self,
        registry: ToolRegistry,
        policy: PolicyMiddleware,
        audit_sink: AuditSink | None = None,
        metrics: RuntimeMetrics | None = None,
    ) -> None:
        self._registry = registry
        self._policy = policy
        self._audit_sink = audit_sink
        self._metrics = metrics

    def execute(self, call: ToolCallContext) -> ToolResult:
        if self._metrics is not None:
            self._metrics.inc("tool.call.total")

        decision = self._policy.before_tool_call(call)
        if decision.decision != PolicyAction.ALLOW:
            if self._metrics is not None:
                self._metrics.inc("tool.call.blocked")
            return blocked_result(call, decision.reason_code, decision.message)

        started = _utc_now()
        try:
            descriptor = self._registry.resolve(call.tool_name)
            handler = apply_execution_decorators(
                descriptor.handler,
                required_args=list(descriptor.metadata.get("required_args", [])),
                allow_state_changing=bool(descriptor.metadata.get("allow_state_changing", True)),
                is_state_changing_call=call.is_state_changing,
                max_attempts=int(descriptor.metadata.get("max_retries", 1)),
                redact_keys=list(descriptor.metadata.get("redact_keys", [])),
                audit_sink=self._audit_sink,
                event_prefix=f"tool.{call.tool_name}",
            )
            output = handler(**call.arguments)
            result = ToolResult(
                schema_version="1.0",
                call_id=call.call_id,
                tool_name=call.tool_name,
                status=ToolStatus.SUCCESS,
                result={"value": output},
                execution=ExecutionMetadata(
                    mode_used=ToolExecutionMode.DETERMINISTIC,
                    started_at_utc=started,
                    finished_at_utc=_utc_now(),
                    timeout_ms=descriptor.timeout_ms,
                ),
                audit=ToolAudit(
                    correlation_id=call.call_id,
                    decision_reason_code=decision.reason_code,
                ),
            )
            if self._metrics is not None:
                self._metrics.inc("tool.call.success")
            return self._policy.after_tool_call(result)
        except KeyError as exc:
            if self._metrics is not None:
                self._metrics.inc("tool.call.failed")
            return ToolResult(
                schema_version="1.0",
                call_id=call.call_id,
                tool_name=call.tool_name,
                status=ToolStatus.ERROR,
                error=NormalizedError(
                    code="TOOL_NOT_FOUND",
                    category="tool_registry",
                    message=str(exc),
                    retryable=False,
                ),
                execution=ExecutionMetadata(
                    mode_used=ToolExecutionMode.DETERMINISTIC,
                    started_at_utc=started,
                    finished_at_utc=_utc_now(),
                ),
                audit=ToolAudit(correlation_id=call.call_id, decision_reason_code=decision.reason_code),
            )
        except Exception as exc:  # pragma: no cover - defensive catch for plugin handlers
            if self._metrics is not None:
                self._metrics.inc("tool.call.failed")
            return ToolResult(
                schema_version="1.0",
                call_id=call.call_id,
                tool_name=call.tool_name,
                status=ToolStatus.ERROR,
                error=NormalizedError(
                    code="TOOL_EXECUTION_ERROR",
                    category="tool_runtime",
                    message=str(exc),
                    retryable=False,
                ),
                execution=ExecutionMetadata(
                    mode_used=ToolExecutionMode.DETERMINISTIC,
                    started_at_utc=started,
                    finished_at_utc=_utc_now(),
                ),
                audit=ToolAudit(correlation_id=call.call_id, decision_reason_code=decision.reason_code),
            )
