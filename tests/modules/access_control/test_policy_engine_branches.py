"""
File: test_policy_engine_branches.py
Path: tests/modules/access_control/test_policy_engine_branches.py
Role: Targeted tests for AccessPolicyEngine decision branches.
Used By:
 - pytest
Depends On:
 - src/access_control/policy_engine.py
 - src/access_control/contracts.py
Notes:
 - Covers wildcard admin, tool-scoped permission, missing base permission, audit-only finalize.
"""

from __future__ import annotations

from src.access_control.contracts import AccessRequest
from src.access_control.policy_engine import AccessControlConfig, AccessPolicyEngine
from src.schemas.tool_io import PolicyAction


def test_admin_wildcard_allows_immediately() -> None:
    engine = AccessPolicyEngine()
    decision = engine.evaluate(
        AccessRequest(
            subject="admin-user",
            roles=["admin"],
            tool_name="any_tool",
            is_state_changing=True,
            is_high_impact=True,
        )
    )
    assert decision.decision == PolicyAction.ALLOW
    assert decision.reason_code == "ACCESS_ALLOWED_ADMIN"


def test_tool_scoped_permission_allows() -> None:
    engine = AccessPolicyEngine(
        AccessControlConfig(
            role_permissions={"custom": {"tool:execute", "tool:my_tool"}},
        )
    )
    decision = engine.evaluate(
        AccessRequest(
            subject="u",
            roles=["custom"],
            tool_name="my_tool",
            is_state_changing=False,
            is_high_impact=False,
        )
    )
    assert decision.decision == PolicyAction.ALLOW
    assert decision.reason_code == "ACCESS_ALLOWED_TOOL_SCOPE"


def test_missing_base_execute_permission_denies() -> None:
    engine = AccessPolicyEngine(
        AccessControlConfig(role_permissions={"guest": set()}),
    )
    decision = engine.evaluate(
        AccessRequest(
            subject="u",
            roles=["guest"],
            tool_name="t",
            is_state_changing=False,
            is_high_impact=False,
            plugin_scope="",
        )
    )
    assert decision.decision == PolicyAction.DENY
    assert decision.reason_code == "ACCESS_DENIED_ROLE_MISSING_PERMISSION"


def test_audit_only_mode_preserves_allow_without_metadata_rewrite() -> None:
    engine = AccessPolicyEngine(AccessControlConfig(audit_only_mode=True))
    decision = engine.evaluate(
        AccessRequest(
            subject="admin-user",
            roles=["admin"],
            tool_name="any",
            is_state_changing=False,
            is_high_impact=False,
        )
    )
    assert decision.decision == PolicyAction.ALLOW
    assert decision.reason_code == "ACCESS_ALLOWED_ADMIN"
    assert "audit_only_original_decision" not in decision.metadata


def test_audit_only_mode_bypasses_deny_with_metadata() -> None:
    engine = AccessPolicyEngine(
        AccessControlConfig(audit_only_mode=True, role_permissions={"guest": set()}),
    )
    decision = engine.evaluate(
        AccessRequest(
            subject="u",
            roles=["guest"],
            tool_name="t",
            is_state_changing=False,
            is_high_impact=False,
            plugin_scope="",
        )
    )
    assert decision.decision == PolicyAction.ALLOW
    assert decision.reason_code == "ACCESS_AUDIT_ONLY_BYPASS"
    assert decision.metadata.get("audit_only_original_decision") == PolicyAction.DENY.value
