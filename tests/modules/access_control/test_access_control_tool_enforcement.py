"""
File: test_access_control_tool_enforcement.py
Path: tests/modules/access_control/test_access_control_tool_enforcement.py
Role: Integration tests for access-control enforcement in deterministic tool execution.
Used By:
 - pytest
Depends On:
 - src/policies/middleware.py
 - src/policies/risk_gates.py
 - src/access_control/policy_engine.py
 - src/tools/executor.py
 - src/tools/registry.py
Notes:
 - Ensures authorization decisions are enforced with deterministic envelopes.
"""

from src.access_control.policy_engine import AccessPolicyEngine
from src.policies.middleware import DeterministicFirstPolicyMiddleware
from src.policies.risk_gates import RiskGateConfig
from src.schemas.tool_io import RiskTier, ToolCallContext, ToolStatus
from src.tools.executor import DeterministicToolExecutor
from src.tools.registry import ToolDescriptor, ToolRegistry


def _call(identity_subject: str, identity_roles: list[str], is_state_changing: bool) -> ToolCallContext:
    return ToolCallContext(
        schema_version="1.0",
        call_id="tc_access",
        session_id="sess_1",
        run_id="run_1",
        job_id="job_1",
        task_id="task_1",
        agent_id="agent_1",
        provider_id="openai",
        tool_name="stateful_tool",
        arguments={"value": 2},
        identity_subject=identity_subject,
        identity_roles=identity_roles,
        is_state_changing=is_state_changing,
        risk_tier=RiskTier.HIGH if is_state_changing else RiskTier.LOW,
    )


def test_tool_execution_blocked_when_access_denied_or_escalated() -> None:
    policy = DeterministicFirstPolicyMiddleware(
        risk_gate_config=RiskGateConfig(access_policy_engine=AccessPolicyEngine())
    )
    registry = ToolRegistry()
    registry.register(ToolDescriptor(name="stateful_tool", handler=lambda value: value + 1))
    executor = DeterministicToolExecutor(registry=registry, policy=policy)

    result = executor.execute(_call(identity_subject="user_low", identity_roles=["reader"], is_state_changing=True))
    assert result.status == ToolStatus.BLOCKED
    assert result.error.code == "POLICY_BLOCKED"
    assert result.error.details == {"reason_code": "ACCESS_REVIEW_REQUIRED_HIGH_IMPACT"}

