"""
File: test_access_control_rbac.py
Path: tests/modules/access_control/test_access_control_rbac.py
Role: Unit tests for RBAC access policy decisions.
Used By:
 - pytest
Depends On:
 - src/access_control/policy_engine.py
 - src/access_control/contracts.py
Notes:
 - Validates allow/deny/escalate and audit-only behavior.
"""

from src.access_control.contracts import AccessRequest
from src.access_control.policy_engine import AccessControlConfig, AccessPolicyEngine
from src.schemas.tool_io import PolicyAction


def test_access_policy_denies_missing_identity_subject() -> None:
    engine = AccessPolicyEngine()
    decision = engine.evaluate(
        AccessRequest(
            subject="",
            roles=["reader"],
            tool_name="sum_tool",
            is_state_changing=False,
            is_high_impact=False,
        )
    )
    assert decision.decision == PolicyAction.DENY
    assert decision.reason_code == "ACCESS_IDENTITY_MISSING"


def test_access_policy_escalates_high_impact_without_permission() -> None:
    engine = AccessPolicyEngine()
    decision = engine.evaluate(
        AccessRequest(
            subject="user_1",
            roles=["reader"],
            tool_name="write_tool",
            is_state_changing=True,
            is_high_impact=True,
        )
    )
    assert decision.decision == PolicyAction.ESCALATE
    assert decision.reason_code == "ACCESS_REVIEW_REQUIRED_HIGH_IMPACT"
    assert decision.review_required is True


def test_access_policy_audit_only_mode_bypasses_non_allow_decisions() -> None:
    engine = AccessPolicyEngine(config=AccessControlConfig(audit_only_mode=True))
    decision = engine.evaluate(
        AccessRequest(
            subject="user_2",
            roles=["reader"],
            tool_name="write_tool",
            is_state_changing=True,
            is_high_impact=True,
        )
    )
    assert decision.decision == PolicyAction.ALLOW
    assert decision.reason_code == "ACCESS_AUDIT_ONLY_BYPASS"


def test_access_policy_denies_missing_plugin_scope_permission() -> None:
    engine = AccessPolicyEngine(
        config=AccessControlConfig(
            role_permissions={
                "reader": {"tool:execute"},
                "plugin_reader": {"tool:execute"},
            }
        )
    )
    decision = engine.evaluate(
        AccessRequest(
            subject="user_plugin",
            roles=["plugin_reader"],
            tool_name="sum_tool",
            is_state_changing=False,
            is_high_impact=False,
            plugin_scope="analytics",
        )
    )
    assert decision.decision == PolicyAction.DENY
    assert decision.reason_code == "ACCESS_DENIED_PLUGIN_SCOPE"


def test_access_policy_allows_when_plugin_scope_permission_present() -> None:
    engine = AccessPolicyEngine(
        config=AccessControlConfig(
            role_permissions={
                "plugin_operator": {"tool:execute", "plugin:analytics:execute"},
            }
        )
    )
    decision = engine.evaluate(
        AccessRequest(
            subject="user_plugin_ok",
            roles=["plugin_operator"],
            tool_name="sum_tool",
            is_state_changing=False,
            is_high_impact=False,
            plugin_scope="analytics",
        )
    )
    assert decision.decision == PolicyAction.ALLOW
