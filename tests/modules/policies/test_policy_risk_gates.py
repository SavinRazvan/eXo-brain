"""
File: test_policy_risk_gates.py
Path: tests/modules/policies/test_policy_risk_gates.py
Role: Unit tests for explicit allow/deny/escalate decisions produced by risk-gate policy middleware.
Used By:
 - pytest
Depends On:
 - src/policies/middleware.py
 - src/policies/risk_gates.py
 - src/tools/executor.py
 - src/tools/registry.py
 - src/schemas/tool_io.py
Notes:
 - Verifies both policy decisions and executor behavior for non-allow outcomes.
"""

from src.policies.middleware import DeterministicFirstPolicyMiddleware
from src.policies.risk_gates import RiskGateConfig
from src.schemas.tool_io import (
    ExecutionMetadata,
    PolicyAction,
    RiskTier,
    ToolAudit,
    ToolCallContext,
    ToolExecutionMode,
    ToolResult,
    ToolStatus,
)
from src.tools.executor import DeterministicToolExecutor
from src.tools.registry import ToolDescriptor, ToolRegistry


def _call(
    call_id: str,
    risk_tier: RiskTier = RiskTier.LOW,
    is_state_changing: bool = False,
) -> ToolCallContext:
    return ToolCallContext(
        schema_version="1.0",
        call_id=call_id,
        session_id="sess_1",
        run_id="run_1",
        job_id="job_1",
        task_id="task_1",
        agent_id="agent_1",
        provider_id="openai",
        tool_name="sum_tool",
        arguments={"a": 2, "b": 3},
        risk_tier=risk_tier,
        is_state_changing=is_state_changing,
    )


def test_policy_allow_for_low_risk_read_only_call() -> None:
    policy = DeterministicFirstPolicyMiddleware()
    decision = policy.before_tool_call(_call(call_id="tc_allow"))

    assert decision.decision == PolicyAction.ALLOW
    assert decision.reason_code == "LOW_RISK_ALLOWED"
    assert decision.enforced_mode is None
    assert decision.review_required is False


def test_policy_deny_blocks_execution_when_risk_tier_is_configured() -> None:
    policy = DeterministicFirstPolicyMiddleware(
        risk_gate_config=RiskGateConfig(deny_risk_tiers={RiskTier.CRITICAL})
    )
    registry = ToolRegistry()
    registry.register(ToolDescriptor(name="sum_tool", handler=lambda a, b: a + b))
    executor = DeterministicToolExecutor(registry=registry, policy=policy)

    call = _call(call_id="tc_deny", risk_tier=RiskTier.CRITICAL, is_state_changing=True)
    decision = policy.before_tool_call(call)
    result = executor.execute(call)

    assert decision.decision == PolicyAction.DENY
    assert decision.reason_code == "RISK_TIER_DENIED"
    assert result.status == ToolStatus.BLOCKED
    assert result.error.code == "POLICY_BLOCKED"
    assert result.error.details == {"reason_code": "RISK_TIER_DENIED"}


def test_policy_escalate_blocks_execution_and_marks_review_required() -> None:
    policy = DeterministicFirstPolicyMiddleware(
        risk_gate_config=RiskGateConfig(escalate_risk_tiers={RiskTier.HIGH}, review_channel="ops-approval")
    )
    registry = ToolRegistry()
    registry.register(ToolDescriptor(name="sum_tool", handler=lambda a, b: a + b))
    executor = DeterministicToolExecutor(registry=registry, policy=policy)

    call = _call(call_id="tc_escalate", risk_tier=RiskTier.HIGH)
    decision = policy.before_tool_call(call)
    result = executor.execute(call)

    assert decision.decision == PolicyAction.ESCALATE
    assert decision.reason_code == "RISK_TIER_REQUIRES_REVIEW"
    assert decision.review_required is True
    assert decision.review_channel == "ops-approval"
    assert decision.enforced_mode == ToolExecutionMode.DETERMINISTIC
    assert result.status == ToolStatus.BLOCKED
    assert result.error.details == {"reason_code": "RISK_TIER_REQUIRES_REVIEW"}


def test_policy_after_tool_call_blocks_missing_audit_correlation() -> None:
    policy = DeterministicFirstPolicyMiddleware()
    malformed = ToolResult(
        schema_version="1.0",
        call_id="tc_postcheck_missing_audit",
        tool_name="sum_tool",
        status=ToolStatus.SUCCESS,
        result={"value": 5},
        execution=ExecutionMetadata(mode_used=ToolExecutionMode.DETERMINISTIC),
        audit=ToolAudit(correlation_id=""),
    )
    result = policy.after_tool_call(malformed)
    assert result.status == ToolStatus.ERROR
    assert result.error.code == "POLICY_POSTCHECK_FAILED"


def test_policy_after_tool_call_blocks_non_deterministic_execution_metadata() -> None:
    policy = DeterministicFirstPolicyMiddleware()
    malformed = ToolResult(
        schema_version="1.0",
        call_id="tc_postcheck_mode",
        tool_name="sum_tool",
        status=ToolStatus.SUCCESS,
        result={"value": 5},
        execution=ExecutionMetadata(mode_used=ToolExecutionMode.PROVIDER_NATIVE),
        audit=ToolAudit(correlation_id="tc_postcheck_mode"),
    )
    result = policy.after_tool_call(malformed)
    assert result.status == ToolStatus.ERROR
    assert result.error.code == "POLICY_POSTCHECK_FAILED"
