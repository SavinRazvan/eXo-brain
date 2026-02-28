"""
File: risk_gates.py
Path: src/policies/risk_gates.py
Role: Risk-gate policy evaluator that maps tool-call context into allow/deny/escalate decisions.
Used By:
 - src/policies/middleware.py
Depends On:
 - src/schemas/tool_io.py
Notes:
 - Defaults preserve deterministic-first behavior while allowing stricter deny/escalate policies via config.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.access_control.contracts import AccessRequest
from src.access_control.policy_engine import AccessPolicyEngine
from src.schemas.tool_io import PolicyAction, PolicyAudit, PolicyDecision, RiskTier, ToolCallContext, ToolExecutionMode


@dataclass(slots=True)
class RiskGateConfig:
    deny_risk_tiers: set[RiskTier] = field(default_factory=set)
    escalate_risk_tiers: set[RiskTier] = field(default_factory=set)
    deny_tools: set[str] = field(default_factory=set)
    escalate_tools: set[str] = field(default_factory=set)
    escalate_state_changing: bool = False
    review_channel: str = "security-review"
    access_policy_engine: AccessPolicyEngine | None = None


class RiskGatePolicy:
    def __init__(self, config: RiskGateConfig | None = None) -> None:
        self._config = config or RiskGateConfig()

    def evaluate(
        self,
        context: ToolCallContext,
        policy_id: str,
        policy_version: str,
    ) -> PolicyDecision:
        if self._config.access_policy_engine is not None:
            access = self._config.access_policy_engine.evaluate(
                AccessRequest(
                    subject=context.identity_subject,
                    roles=list(context.identity_roles),
                    tool_name=context.tool_name,
                    is_state_changing=context.is_state_changing,
                    is_high_impact=context.risk_tier in {RiskTier.HIGH, RiskTier.CRITICAL},
                )
            )
            if access.decision != PolicyAction.ALLOW:
                return self._decision(
                    context=context,
                    action=access.decision,
                    reason_code=access.reason_code,
                    message=access.message,
                    policy_id=policy_id,
                    policy_version=policy_version,
                    review_required=access.review_required,
                    review_channel=access.review_channel,
                    enforced_mode=ToolExecutionMode.DETERMINISTIC,
                )

        if context.tool_name in self._config.deny_tools:
            return self._decision(
                context=context,
                action=PolicyAction.DENY,
                reason_code="TOOL_DENIED",
                message="Tool is blocked by policy configuration.",
                policy_id=policy_id,
                policy_version=policy_version,
            )

        if context.risk_tier in self._config.deny_risk_tiers:
            return self._decision(
                context=context,
                action=PolicyAction.DENY,
                reason_code="RISK_TIER_DENIED",
                message=f"Risk tier '{context.risk_tier.value}' is blocked by policy configuration.",
                policy_id=policy_id,
                policy_version=policy_version,
            )

        if context.tool_name in self._config.escalate_tools:
            return self._decision(
                context=context,
                action=PolicyAction.ESCALATE,
                reason_code="TOOL_REQUIRES_REVIEW",
                message="Tool requires manual review before execution.",
                policy_id=policy_id,
                policy_version=policy_version,
                review_required=True,
                review_channel=self._config.review_channel,
                enforced_mode=ToolExecutionMode.DETERMINISTIC,
            )

        if context.risk_tier in self._config.escalate_risk_tiers:
            return self._decision(
                context=context,
                action=PolicyAction.ESCALATE,
                reason_code="RISK_TIER_REQUIRES_REVIEW",
                message=f"Risk tier '{context.risk_tier.value}' requires manual review.",
                policy_id=policy_id,
                policy_version=policy_version,
                review_required=True,
                review_channel=self._config.review_channel,
                enforced_mode=ToolExecutionMode.DETERMINISTIC,
            )

        if context.is_state_changing and self._config.escalate_state_changing:
            return self._decision(
                context=context,
                action=PolicyAction.ESCALATE,
                reason_code="STATE_CHANGE_REQUIRES_REVIEW",
                message="State-changing tool requires manual review.",
                policy_id=policy_id,
                policy_version=policy_version,
                review_required=True,
                review_channel=self._config.review_channel,
                enforced_mode=ToolExecutionMode.DETERMINISTIC,
            )

        if context.risk_tier in {RiskTier.HIGH, RiskTier.CRITICAL} or context.is_state_changing:
            return self._decision(
                context=context,
                action=PolicyAction.ALLOW,
                reason_code="RISK_WRITE_REQUIRES_DETERMINISTIC",
                message="State-changing or high-impact tools require deterministic mode.",
                policy_id=policy_id,
                policy_version=policy_version,
                enforced_mode=ToolExecutionMode.DETERMINISTIC,
            )

        return self._decision(
            context=context,
            action=PolicyAction.ALLOW,
            reason_code="LOW_RISK_ALLOWED",
            message="Low-risk read-only tool allowed.",
            policy_id=policy_id,
            policy_version=policy_version,
        )

    def _decision(
        self,
        context: ToolCallContext,
        action: PolicyAction,
        reason_code: str,
        message: str,
        policy_id: str,
        policy_version: str,
        review_required: bool = False,
        review_channel: str | None = None,
        enforced_mode: ToolExecutionMode | None = None,
    ) -> PolicyDecision:
        return PolicyDecision(
            schema_version="1.0",
            decision=action,
            reason_code=reason_code,
            message=message,
            enforced_mode=enforced_mode,
            review_required=review_required,
            review_channel=review_channel,
            audit=PolicyAudit(
                policy_id=policy_id,
                policy_version=policy_version,
                correlation_id=context.call_id,
            ),
        )
