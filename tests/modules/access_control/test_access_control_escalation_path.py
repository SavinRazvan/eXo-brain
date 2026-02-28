"""
File: test_access_control_escalation_path.py
Path: tests/modules/access_control/test_access_control_escalation_path.py
Role: Integration test for access-control escalation metadata in policy decisions.
Used By:
 - pytest
Depends On:
 - src/policies/middleware.py
 - src/policies/risk_gates.py
 - src/access_control/policy_engine.py
 - src/schemas/tool_io.py
Notes:
 - Confirms review-required path surfaces channel and deterministic enforcement.
"""

from src.access_control.policy_engine import AccessControlConfig, AccessPolicyEngine
from src.policies.middleware import DeterministicFirstPolicyMiddleware
from src.policies.risk_gates import RiskGateConfig
from src.schemas.tool_io import PolicyAction, RiskTier, ToolCallContext, ToolExecutionMode


def test_policy_escalation_path_for_high_impact_access_control() -> None:
    policy = DeterministicFirstPolicyMiddleware(
        risk_gate_config=RiskGateConfig(
            access_policy_engine=AccessPolicyEngine(
                config=AccessControlConfig(review_channel="manual-approval")
            )
        )
    )
    decision = policy.before_tool_call(
        ToolCallContext(
            schema_version="1.0",
            call_id="tc_escalate_ac",
            session_id="sess_1",
            run_id="run_1",
            job_id="job_1",
            task_id="task_1",
            agent_id="agent_1",
            provider_id="openai",
            tool_name="stateful_tool",
            arguments={"value": 1},
            identity_subject="user_reader",
            identity_roles=["reader"],
            is_state_changing=True,
            risk_tier=RiskTier.HIGH,
        )
    )
    assert decision.decision == PolicyAction.ESCALATE
    assert decision.reason_code == "ACCESS_REVIEW_REQUIRED_HIGH_IMPACT"
    assert decision.review_required is True
    assert decision.review_channel == "manual-approval"
    assert decision.enforced_mode == ToolExecutionMode.DETERMINISTIC
