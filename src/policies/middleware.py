"""
File: middleware.py
Path: src/policies/middleware.py
Role: Policy middleware contracts and default deterministic-first implementation.
Used By:
 - src/runtime/mode_selector.py
 - src/tools/executor.py
 - src/core/orchestrator.py
Depends On:
 - src/schemas/tool_io.py
Notes:
 - Policy decisions are auditable and must include reason codes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from src.policies.risk_gates import RiskGateConfig, RiskGatePolicy
from src.tenancy.policy_overlay import TenantPolicyOverlayStore
from src.schemas.tool_io import (
    ExecutionMetadata,
    NormalizedError,
    PolicyDecision,
    ToolExecutionMode,
    ToolCallContext,
    ToolResult,
    ToolStatus,
)


class PolicyMiddleware(ABC):
    @abstractmethod
    def before_tool_call(self, context: ToolCallContext) -> PolicyDecision:
        raise NotImplementedError

    @abstractmethod
    def after_tool_call(self, result: ToolResult) -> ToolResult:
        raise NotImplementedError

    @abstractmethod
    def before_output(self, output: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class DeterministicFirstPolicyMiddleware(PolicyMiddleware):
    def __init__(
        self,
        policy_id: str = "policy-risk-gate-v1",
        policy_version: str = "1.0.0",
        risk_gate_config: RiskGateConfig | None = None,
        tenant_policy_overlays: TenantPolicyOverlayStore | None = None,
    ) -> None:
        self._policy_id = policy_id
        self._policy_version = policy_version
        self._risk_gates = RiskGatePolicy(config=risk_gate_config)
        self._tenant_policy_overlays = tenant_policy_overlays

    def before_tool_call(self, context: ToolCallContext) -> PolicyDecision:
        overlay = (
            self._tenant_policy_overlays.get_overlay(context.tenant_id)
            if self._tenant_policy_overlays is not None
            else None
        )
        return self._risk_gates.evaluate(
            context=context,
            policy_id=self._policy_id,
            policy_version=self._policy_version,
            tenant_overlay=overlay,
        )

    def after_tool_call(self, result: ToolResult) -> ToolResult:
        if result.audit is None or not str(result.audit.correlation_id).strip():
            return self._postcheck_error(result, "missing audit correlation_id")
        if result.execution.mode_used != ToolExecutionMode.DETERMINISTIC:
            return self._postcheck_error(result, "non-deterministic execution metadata")
        if result.status == ToolStatus.SUCCESS and result.result is None:
            return self._postcheck_error(result, "success result is missing payload")
        return result

    def before_output(self, output: dict[str, Any]) -> dict[str, Any]:
        return output

    def _postcheck_error(self, result: ToolResult, reason: str) -> ToolResult:
        return ToolResult(
            schema_version=result.schema_version,
            call_id=result.call_id,
            tool_name=result.tool_name,
            status=ToolStatus.ERROR,
            error=NormalizedError(
                code="POLICY_POSTCHECK_FAILED",
                category="policy",
                message=f"Policy post-check failed: {reason}",
                retryable=False,
            ),
            execution=ExecutionMetadata(mode_used=ToolExecutionMode.DETERMINISTIC),
            audit=result.audit,
        )

