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

from datetime import datetime, timezone
from typing import Any

from src.mcp.mcp_client_adapter import McpClientAdapter
from src.mcp.mcp_registry import McpHealthState, McpRegistry, McpTrustTier
from src.policies.middleware import PolicyMiddleware
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
    def __init__(self, registry: McpRegistry, client: McpClientAdapter, policy: PolicyMiddleware) -> None:
        self._registry = registry
        self._client = client
        self._policy = policy

    async def execute(
        self,
        server_id: str,
        tool_name: str,
        context: ToolCallContext,
    ) -> ToolResult:
        decision = self._policy.before_tool_call(context)
        if decision.decision != PolicyAction.ALLOW:
            return blocked_result(context, decision.reason_code, decision.message)

        started = _utc_now()
        try:
            server = self._registry.get_server(server_id)
            await self._sync_server_health(server_id)
            self._enforce_trust_tier(server.trust_tier, context)
            output = await self._client.call_tool(server_id=server_id, tool_name=tool_name, arguments=context.arguments)
            result = ToolResult(
                schema_version="1.0",
                call_id=context.call_id,
                tool_name=context.tool_name,
                status=ToolStatus.SUCCESS,
                result={"value": output},
                execution=ExecutionMetadata(
                    mode_used=ToolExecutionMode.DETERMINISTIC,
                    started_at_utc=started,
                    finished_at_utc=_utc_now(),
                    timeout_ms=server.timeout_ms,
                ),
                audit=ToolAudit(
                    correlation_id=context.call_id,
                    decision_reason_code=decision.reason_code,
                ),
            )
            return self._policy.after_tool_call(result)
        except (KeyError, ValueError) as exc:
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
                ),
                audit=ToolAudit(correlation_id=context.call_id, decision_reason_code=decision.reason_code),
            )
        except Exception as exc:  # pragma: no cover - defensive path
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
                ),
                audit=ToolAudit(correlation_id=context.call_id, decision_reason_code=decision.reason_code),
            )

    async def _sync_server_health(self, server_id: str) -> None:
        response = await self._client.healthcheck(server_id)
        raw_state = str(response.get("state", "healthy")).strip().lower()
        reason = str(response.get("reason", "")).strip()
        state = {
            "healthy": McpHealthState.HEALTHY,
            "degraded": McpHealthState.DEGRADED,
            "unavailable": McpHealthState.UNAVAILABLE,
        }.get(raw_state, McpHealthState.DEGRADED)
        self._registry.set_server_health(server_id=server_id, state=state, reason=reason)
        if state == McpHealthState.UNAVAILABLE:
            raise ValueError(f"MCP server '{server_id}' is unavailable: {reason or 'healthcheck failed'}")

    def _enforce_trust_tier(self, trust_tier: McpTrustTier, context: ToolCallContext) -> None:
        if trust_tier == McpTrustTier.TRUSTED:
            return
        if trust_tier == McpTrustTier.RESTRICTED and context.is_state_changing:
            raise ValueError("Restricted MCP tier blocks state-changing tool calls")
        if trust_tier == McpTrustTier.SANDBOXED and (context.is_state_changing or context.risk_tier.value in {"high", "critical"}):
            raise ValueError("Sandboxed MCP tier blocks high-impact or state-changing calls")
