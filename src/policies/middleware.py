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

from src.schemas.tool_io import (
    PolicyAction,
    PolicyAudit,
    PolicyDecision,
    RiskTier,
    ToolCallContext,
    ToolExecutionMode,
    ToolResult,
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
    def __init__(self, policy_id: str = "policy-risk-gate-v1", policy_version: str = "1.0.0") -> None:
        self._policy_id = policy_id
        self._policy_version = policy_version

    def before_tool_call(self, context: ToolCallContext) -> PolicyDecision:
        if context.risk_tier in {RiskTier.HIGH, RiskTier.CRITICAL} or context.is_state_changing:
            return self._decision(
                context=context,
                action=PolicyAction.ALLOW,
                reason_code="RISK_WRITE_REQUIRES_DETERMINISTIC",
                message="State-changing or high-risk tools require deterministic mode.",
                enforced_mode=ToolExecutionMode.DETERMINISTIC,
            )

        return self._decision(
            context=context,
            action=PolicyAction.ALLOW,
            reason_code="LOW_RISK_ALLOWED",
            message="Low-risk read-only tool allowed.",
            enforced_mode=None,
        )

    def after_tool_call(self, result: ToolResult) -> ToolResult:
        return result

    def before_output(self, output: dict[str, Any]) -> dict[str, Any]:
        return output

    def _decision(
        self,
        context: ToolCallContext,
        action: PolicyAction,
        reason_code: str,
        message: str,
        enforced_mode: ToolExecutionMode | None,
    ) -> PolicyDecision:
        return PolicyDecision(
            schema_version="1.0",
            decision=action,
            reason_code=reason_code,
            message=message,
            enforced_mode=enforced_mode,
            audit=PolicyAudit(
                policy_id=self._policy_id,
                policy_version=self._policy_version,
                correlation_id=context.call_id,
            ),
        )
