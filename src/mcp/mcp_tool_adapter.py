"""
File: mcp_tool_adapter.py
Path: src/mcp/mcp_tool_adapter.py
Role: MCP tool execution adapter with trust-tier and policy enforcement.
Used By:
 - src/tools/executor.py
 - src/core/orchestrator.py
Depends On:
 - src/mcp/mcp_registry.py
 - src/mcp/mcp_client_adapter.py
 - src/policies/middleware.py
 - src/schemas/tool_io.py
Notes:
 - State-changing or high-impact calls on restricted tiers are blocked by default.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from time import perf_counter
from typing import Any

from src.mcp.mcp_client_adapter import McpClientAdapter
from src.mcp.mcp_registry import McpHealthState, McpRegistry, McpTrustTier
from src.observability.logging import LogLevel, StructuredLogger
from src.policies.middleware import PolicyMiddleware
from src.resilience.circuit_breaker import CircuitBreaker
from src.resilience.dlq import DeadLetterQueue, DlqRecord
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


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class McpToolAdapter:
    def __init__(
        self,
        registry: McpRegistry,
        client: McpClientAdapter,
        policy: PolicyMiddleware,
        circuit_breaker: CircuitBreaker | None = None,
        dlq: DeadLetterQueue | None = None,
        logger: StructuredLogger | None = None,
    ) -> None:
        self._registry = registry
        self._client = client
        self._policy = policy
        self._circuit_breaker = circuit_breaker or CircuitBreaker()
        self._dlq = dlq or DeadLetterQueue()
        self._logger = logger

    async def execute(
        self,
        server_id: str,
        tool_name: str,
        context: ToolCallContext,
    ) -> ToolResult:
        decision = self._policy.before_tool_call(context)
        if decision.decision != PolicyAction.ALLOW:
            self._log(
                level=LogLevel.WARNING,
                event="mcp.policy.blocked",
                message=f"Policy blocked MCP tool '{tool_name}'",
                correlation_id=context.call_id,
                context={"server_id": server_id, "tool_name": tool_name, "reason_code": decision.reason_code},
            )
            return blocked_result(context, decision.reason_code, decision.message)

        started = _utc_now()
        started_clock = perf_counter()
        circuit_key = f"{server_id}:{tool_name}"
        if not self._circuit_breaker.allow(circuit_key):
            self._log(
                level=LogLevel.ERROR,
                event="mcp.circuit.open",
                message=f"Circuit open for '{circuit_key}'",
                correlation_id=context.call_id,
                context={"server_id": server_id, "tool_name": tool_name},
            )
            return ToolResult(
                schema_version="1.0",
                call_id=context.call_id,
                tool_name=context.tool_name,
                status=ToolStatus.ERROR,
                error=NormalizedError(
                    code="MCP_CIRCUIT_OPEN",
                    category="mcp_adapter",
                    message=f"Circuit is open for '{circuit_key}'",
                    retryable=True,
                ),
                execution=ExecutionMetadata(
                    mode_used=ToolExecutionMode.DETERMINISTIC,
                    started_at_utc=started,
                    finished_at_utc=_utc_now(),
                    duration_ms=int((perf_counter() - started_clock) * 1000),
                ),
                audit=ToolAudit(correlation_id=context.call_id, decision_reason_code=decision.reason_code),
            )

        server_timeout_ms = 30000
        max_retries = 0
        attempt = 1
        try:
            server = self._registry.get_server(server_id)
            server_timeout_ms = server.timeout_ms
            max_retries = self._resolve_max_retries(server.metadata)
            await self._sync_server_health(server_id, server.timeout_ms, context.call_id)
            self._enforce_trust_tier(server.trust_tier, context)
            self._log(
                level=LogLevel.INFO,
                event="mcp.call.started",
                message=f"Calling MCP tool '{tool_name}'",
                correlation_id=context.call_id,
                context={
                    "server_id": server_id,
                    "tool_name": tool_name,
                    "trust_tier": server.trust_tier.value,
                    "timeout_ms": server.timeout_ms,
                    "max_retries": max_retries,
                },
            )
            while True:
                try:
                    output = await asyncio.wait_for(
                        self._client.call_tool(server_id=server_id, tool_name=tool_name, arguments=context.arguments),
                        timeout=max(server.timeout_ms, 1) / 1000.0,
                    )
                    result = ToolResult(
                        schema_version="1.0",
                        call_id=context.call_id,
                        tool_name=context.tool_name,
                        status=ToolStatus.SUCCESS,
                        result={
                            "value": output,
                            "mcp_observability": {
                                "server_id": server_id,
                                "trust_tier": server.trust_tier.value,
                                "attempt": attempt,
                                "max_retries": max_retries,
                            },
                        },
                        execution=ExecutionMetadata(
                            mode_used=ToolExecutionMode.DETERMINISTIC,
                            started_at_utc=started,
                            finished_at_utc=_utc_now(),
                            duration_ms=int((perf_counter() - started_clock) * 1000),
                            timeout_ms=server.timeout_ms,
                            attempt=attempt,
                        ),
                        audit=ToolAudit(
                            correlation_id=context.call_id,
                            decision_reason_code=decision.reason_code,
                        ),
                    )
                    self._circuit_breaker.record_success(circuit_key)
                    self._log(
                        level=LogLevel.INFO,
                        event="mcp.call.succeeded",
                        message=f"MCP tool '{tool_name}' succeeded",
                        correlation_id=context.call_id,
                        context={"server_id": server_id, "attempt": attempt},
                    )
                    return self._policy.after_tool_call(result)
                except TimeoutError:
                    self._circuit_breaker.record_failure(circuit_key)
                    self._log(
                        level=LogLevel.WARNING,
                        event="mcp.call.timeout",
                        message=f"MCP tool '{tool_name}' timed out",
                        correlation_id=context.call_id,
                        context={"server_id": server_id, "attempt": attempt, "timeout_ms": server.timeout_ms},
                    )
                    if attempt <= max_retries:
                        attempt += 1
                        self._log(
                            level=LogLevel.INFO,
                            event="mcp.call.retry",
                            message=f"Retrying MCP tool '{tool_name}' after timeout",
                            correlation_id=context.call_id,
                            context={"server_id": server_id, "attempt": attempt, "max_retries": max_retries},
                        )
                        continue
                    self._dlq.push(
                        DlqRecord(
                            correlation_id=context.call_id,
                            reason_code="MCP_TIMEOUT",
                            payload={
                                "server_id": server_id,
                                "tool_name": tool_name,
                                "attempt": attempt,
                                "max_retries": max_retries,
                            },
                        )
                    )
                    return ToolResult(
                        schema_version="1.0",
                        call_id=context.call_id,
                        tool_name=context.tool_name,
                        status=ToolStatus.TIMEOUT,
                        error=NormalizedError(
                            code="MCP_TIMEOUT",
                            category="mcp_adapter",
                            message=(
                                f"MCP call timed out after {attempt} attempt(s) "
                                f"for server '{server_id}' and tool '{tool_name}'"
                            ),
                            retryable=True,
                            details={"attempt": attempt, "max_retries": max_retries, "timeout_ms": server.timeout_ms},
                        ),
                        execution=ExecutionMetadata(
                            mode_used=ToolExecutionMode.DETERMINISTIC,
                            started_at_utc=started,
                            finished_at_utc=_utc_now(),
                            duration_ms=int((perf_counter() - started_clock) * 1000),
                            timeout_ms=server.timeout_ms,
                            attempt=attempt,
                        ),
                        audit=ToolAudit(correlation_id=context.call_id, decision_reason_code=decision.reason_code),
                    )
        except (KeyError, ValueError) as exc:
            self._circuit_breaker.record_failure(circuit_key)
            self._log(
                level=LogLevel.ERROR,
                event="mcp.call.validation_error",
                message=f"MCP validation failed for '{tool_name}'",
                correlation_id=context.call_id,
                context={"server_id": server_id, "tool_name": tool_name, "error": str(exc)},
            )
            self._dlq.push(
                DlqRecord(
                    correlation_id=context.call_id,
                    reason_code="MCP_VALIDATION_ERROR",
                    payload={"server_id": server_id, "tool_name": tool_name, "error": str(exc)},
                )
            )
            return ToolResult(
                schema_version="1.0",
                call_id=context.call_id,
                tool_name=context.tool_name,
                status=ToolStatus.ERROR,
                error=NormalizedError(
                    code="MCP_VALIDATION_ERROR",
                    category="mcp_adapter",
                    message=str(exc),
                    retryable=False,
                ),
                execution=ExecutionMetadata(
                    mode_used=ToolExecutionMode.DETERMINISTIC,
                    started_at_utc=started,
                    finished_at_utc=_utc_now(),
                    duration_ms=int((perf_counter() - started_clock) * 1000),
                    timeout_ms=server_timeout_ms,
                    attempt=attempt,
                ),
                audit=ToolAudit(correlation_id=context.call_id, decision_reason_code=decision.reason_code),
            )
        except Exception as exc:  # pragma: no cover - defensive path
            self._circuit_breaker.record_failure(circuit_key)
            self._log(
                level=LogLevel.ERROR,
                event="mcp.call.execution_error",
                message=f"MCP execution failed for '{tool_name}'",
                correlation_id=context.call_id,
                context={"server_id": server_id, "tool_name": tool_name, "error": str(exc)},
            )
            self._dlq.push(
                DlqRecord(
                    correlation_id=context.call_id,
                    reason_code="MCP_EXECUTION_ERROR",
                    payload={"server_id": server_id, "tool_name": tool_name, "error": str(exc)},
                )
            )
            return ToolResult(
                schema_version="1.0",
                call_id=context.call_id,
                tool_name=context.tool_name,
                status=ToolStatus.ERROR,
                error=NormalizedError(
                    code="MCP_EXECUTION_ERROR",
                    category="mcp_adapter",
                    message=str(exc),
                    retryable=False,
                ),
                execution=ExecutionMetadata(
                    mode_used=ToolExecutionMode.DETERMINISTIC,
                    started_at_utc=started,
                    finished_at_utc=_utc_now(),
                    duration_ms=int((perf_counter() - started_clock) * 1000),
                    timeout_ms=server_timeout_ms,
                    attempt=attempt,
                ),
                audit=ToolAudit(correlation_id=context.call_id, decision_reason_code=decision.reason_code),
            )

    async def _sync_server_health(self, server_id: str, timeout_ms: int, correlation_id: str) -> None:
        self._log(
            level=LogLevel.DEBUG,
            event="mcp.healthcheck.started",
            message=f"Running MCP healthcheck for '{server_id}'",
            correlation_id=correlation_id,
            context={"server_id": server_id, "timeout_ms": timeout_ms},
        )
        response = await asyncio.wait_for(
            self._client.healthcheck(server_id),
            timeout=max(timeout_ms, 1) / 1000.0,
        )
        raw_state = str(response.get("state", "healthy")).strip().lower()
        reason = str(response.get("reason", "")).strip()
        state = {
            "healthy": McpHealthState.HEALTHY,
            "degraded": McpHealthState.DEGRADED,
            "unavailable": McpHealthState.UNAVAILABLE,
        }.get(raw_state, McpHealthState.DEGRADED)
        self._registry.set_server_health(server_id=server_id, state=state, reason=reason)
        self._log(
            level=LogLevel.INFO if state == McpHealthState.HEALTHY else LogLevel.WARNING,
            event="mcp.healthcheck.updated",
            message=f"MCP healthcheck updated server '{server_id}'",
            correlation_id=correlation_id,
            context={"server_id": server_id, "state": state.value, "reason": reason},
        )
        if state == McpHealthState.UNAVAILABLE:
            raise ValueError(f"MCP server '{server_id}' is unavailable: {reason or 'healthcheck failed'}")

    def _enforce_trust_tier(self, trust_tier: McpTrustTier, context: ToolCallContext) -> None:
        self._log(
            level=LogLevel.DEBUG,
            event="mcp.trust_tier.checked",
            message=f"Applying MCP trust-tier checks for '{context.tool_name}'",
            correlation_id=context.call_id,
            context={
                "trust_tier": trust_tier.value,
                "is_state_changing": context.is_state_changing,
                "risk_tier": context.risk_tier.value,
            },
        )
        if trust_tier == McpTrustTier.TRUSTED:
            return
        if trust_tier == McpTrustTier.RESTRICTED and context.is_state_changing:
            raise ValueError("Restricted MCP tier blocks state-changing tool calls")
        if trust_tier == McpTrustTier.SANDBOXED and (context.is_state_changing or context.risk_tier.value in {"high", "critical"}):
            raise ValueError("Sandboxed MCP tier blocks high-impact or state-changing calls")

    @staticmethod
    def _resolve_max_retries(metadata: dict[str, Any]) -> int:
        raw_value = metadata.get("max_retries", 0)
        try:
            return max(0, int(raw_value))
        except (TypeError, ValueError):
            return 0

    def _log(
        self,
        level: LogLevel,
        event: str,
        message: str,
        correlation_id: str,
        context: dict[str, Any],
    ) -> None:
        if self._logger is None:
            return
        self._logger.log(
            level=level,
            event=event,
            message=message,
            correlation_id=correlation_id,
            context=context,
        )
