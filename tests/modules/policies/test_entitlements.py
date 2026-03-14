"""
File: test_entitlements.py
Path: tests/modules/policies/test_entitlements.py
Role: Unit tests for governance entitlement tier resolution and feature gating decisions.
Used By:
 - pytest
Depends On:
 - src/policies/entitlements.py
 - src/api/middleware/entitlements.py
 - src/identity/contracts.py
Notes:
 - Validates deterministic fail-closed entitlement decisions and feature mapping.
"""

from src.api.middleware.entitlements import evaluate_feature_entitlement, required_feature_for_governance_overlay
from src.identity.contracts import IdentityContext
from src.policies.entitlements import EntitledFeature, EntitlementTier, resolve_tier_from_roles
from src.schemas.tool_io import PolicyAction


def _identity(*roles: str) -> IdentityContext:
    return IdentityContext(subject="tester", tenant_id="t1", roles=list(roles))


def test_resolve_tier_from_roles_defaults_to_foundation() -> None:
    assert resolve_tier_from_roles(["user", "admin"]) == EntitlementTier.FOUNDATION


def test_resolve_tier_from_roles_supports_pro_and_enterprise_markers() -> None:
    assert resolve_tier_from_roles(["entitlement:pro"]) == EntitlementTier.PRO
    assert resolve_tier_from_roles(["entitlement_enterprise"]) == EntitlementTier.ENTERPRISE


def test_evaluate_feature_entitlement_denies_when_required_tier_missing() -> None:
    decision = evaluate_feature_entitlement(
        identity=_identity("user"),
        feature=EntitledFeature.GOVERNANCE_INGRESS_PROFILE,
    )
    assert decision.decision == PolicyAction.DENY
    assert decision.reason_code == "ENTITLEMENT_TIER_REQUIRED"
    assert decision.required_tier == EntitlementTier.PRO
    assert decision.current_tier == EntitlementTier.FOUNDATION


def test_evaluate_feature_entitlement_allows_when_required_tier_present() -> None:
    decision = evaluate_feature_entitlement(
        identity=_identity("entitlement_pro"),
        feature=EntitledFeature.GOVERNANCE_INGRESS_PROFILE,
    )
    assert decision.decision == PolicyAction.ALLOW
    assert decision.reason_code == "ENTITLEMENT_ALLOWED"


def test_required_feature_for_governance_overlay_selects_highest_tier_feature() -> None:
    assert (
        required_feature_for_governance_overlay({"ingress_profile": "strict"})
        == EntitledFeature.GOVERNANCE_INGRESS_PROFILE
    )
    assert (
        required_feature_for_governance_overlay({"ingress_custom_rules": [{"rule": "x"}]})
        == EntitledFeature.GOVERNANCE_INGRESS_CUSTOM_RULES
    )
    assert (
        required_feature_for_governance_overlay({"signed_gate_plugin_ref": "plugin://corp/signed"})
        == EntitledFeature.GOVERNANCE_INGRESS_SIGNED_PLUGINS
    )
