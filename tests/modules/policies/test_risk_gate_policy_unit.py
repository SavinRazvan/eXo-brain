"""
File: test_risk_gate_policy_unit.py
Path: tests/modules/policies/test_risk_gate_policy_unit.py
Role: Direct unit tests for RiskGatePolicy branches not exercised via middleware-only suites.
Used By:
 - pytest
Depends On:
 - src/policies/risk_gates.py
 - src/access_control/contracts.py
 - src/schemas/tool_io.py
Notes:
 - Covers access-engine short-circuit, tool lists, and tenant overlay parsing.
"""

from src.access_control.contracts import AccessDecision, AccessRequest
from src.policies.risk_gates import RiskGateConfig, RiskGatePolicy
from src.schemas.tool_io import PolicyAction, RiskTier, ToolCallContext, ToolExecutionMode


def _ctx(
    *,
    tool_name: str = "sum_tool",
    risk_tier: RiskTier = RiskTier.LOW,
    is_state_changing: bool = False,
    subject: str = "user-1",
) -> ToolCallContext:
    return ToolCallContext(
        schema_version="1.0",
        call_id="c1",
        session_id="s1",
        run_id="r1",
        job_id="j1",
        task_id="t1",
        agent_id="a1",
        provider_id="openai",
        tool_name=tool_name,
        arguments={},
        tenant_id="tenant-a",
        identity_subject=subject,
        identity_roles=["operator"],
        risk_tier=risk_tier,
        is_state_changing=is_state_changing,
    )


class _StubDenyEngine:
    def evaluate(self, request: AccessRequest) -> AccessDecision:  # noqa: ARG002
        return AccessDecision(
            decision=PolicyAction.DENY,
            reason_code="ACCESS_UNIT_DENY",
            message="blocked by stub",
        )


def test_access_policy_engine_deny_short_circuits_risk_rules() -> None:
    policy = RiskGatePolicy(RiskGateConfig(access_policy_engine=_StubDenyEngine()))
    decision = policy.evaluate(_ctx(tool_name="sum_tool"), "pol", "1.0.0")
    assert decision.decision == PolicyAction.DENY
    assert decision.reason_code == "ACCESS_UNIT_DENY"
    assert decision.enforced_mode == ToolExecutionMode.DETERMINISTIC


def test_deny_tools_blocks_before_risk_tier() -> None:
    policy = RiskGatePolicy(RiskGateConfig(deny_tools={"sum_tool"}))
    decision = policy.evaluate(_ctx(tool_name="sum_tool"), "pol", "1.0.0")
    assert decision.decision == PolicyAction.DENY
    assert decision.reason_code == "TOOL_DENIED"


def test_escalate_tools_requires_review() -> None:
    policy = RiskGatePolicy(RiskGateConfig(escalate_tools={"sum_tool"}, review_channel="sec"))
    decision = policy.evaluate(_ctx(tool_name="sum_tool"), "pol", "1.0.0")
    assert decision.decision == PolicyAction.ESCALATE
    assert decision.reason_code == "TOOL_REQUIRES_REVIEW"
    assert decision.review_channel == "sec"


def test_high_risk_read_only_allows_with_enforced_deterministic() -> None:
    policy = RiskGatePolicy()
    decision = policy.evaluate(
        _ctx(risk_tier=RiskTier.HIGH, is_state_changing=False),
        "pol",
        "1.0.0",
    )
    assert decision.decision == PolicyAction.ALLOW
    assert decision.reason_code == "RISK_WRITE_REQUIRES_DETERMINISTIC"
    assert decision.enforced_mode == ToolExecutionMode.DETERMINISTIC


def test_tenant_overlay_str_set_list_parses_and_strips() -> None:
    policy = RiskGatePolicy(RiskGateConfig())
    decision = policy.evaluate(
        _ctx(tool_name="blocked_tool"),
        "pol",
        "1.0.0",
        tenant_overlay={"deny_tools": ["  blocked_tool  ", "  ", ""]},
    )
    assert decision.decision == PolicyAction.DENY


def test_tenant_overlay_non_list_preserves_base_sets() -> None:
    base = RiskGateConfig(deny_tools={"keep_me"})
    policy = RiskGatePolicy(base)
    decision = policy.evaluate(
        _ctx(tool_name="keep_me"),
        "pol",
        "1.0.0",
        tenant_overlay={"deny_tools": "not-a-list"},
    )
    assert decision.decision == PolicyAction.DENY


def test_low_risk_read_only_hits_default_allow_path() -> None:
    policy = RiskGatePolicy()
    decision = policy.evaluate(_ctx(risk_tier=RiskTier.LOW, is_state_changing=False), "pol", "1.0.0")
    assert decision.decision == PolicyAction.ALLOW
    assert decision.reason_code == "LOW_RISK_ALLOWED"
    assert decision.enforced_mode is None


def test_escalate_risk_tier_branch() -> None:
    policy = RiskGatePolicy(
        RiskGateConfig(escalate_risk_tiers={RiskTier.MEDIUM}, review_channel="tier-review")
    )
    decision = policy.evaluate(_ctx(risk_tier=RiskTier.MEDIUM), "pol", "1.0.0")
    assert decision.decision == PolicyAction.ESCALATE
    assert decision.reason_code == "RISK_TIER_REQUIRES_REVIEW"


def test_escalate_state_changing_branch() -> None:
    policy = RiskGatePolicy(RiskGateConfig(escalate_state_changing=True))
    decision = policy.evaluate(
        _ctx(risk_tier=RiskTier.LOW, is_state_changing=True),
        "pol",
        "1.0.0",
    )
    assert decision.decision == PolicyAction.ESCALATE
    assert decision.reason_code == "STATE_CHANGE_REQUIRES_REVIEW"


def test_tenant_overlay_non_list_for_escalate_tools_preserves_base() -> None:
    policy = RiskGatePolicy(RiskGateConfig(escalate_tools={"sum_tool"}))
    decision = policy.evaluate(
        _ctx(tool_name="sum_tool"),
        "pol",
        "1.0.0",
        tenant_overlay={"escalate_tools": {"not": "list"}},
    )
    assert decision.decision == PolicyAction.ESCALATE


def test_tenant_overlay_invalid_risk_tier_strings_are_skipped() -> None:
    policy = RiskGatePolicy(RiskGateConfig(deny_risk_tiers={RiskTier.MEDIUM}))
    decision = policy.evaluate(
        _ctx(risk_tier=RiskTier.MEDIUM),
        "pol",
        "1.0.0",
        tenant_overlay={"deny_risk_tiers": ["medium", "not-a-tier"]},
    )
    assert decision.decision == PolicyAction.DENY
