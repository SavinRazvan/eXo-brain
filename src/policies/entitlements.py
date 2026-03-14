"""
File: entitlements.py
Path: src/policies/entitlements.py
Role: Tier contracts and feature entitlement policy mapping for governance controls.
Used By:
 - src/api/middleware/entitlements.py
 - src/api/routers/tenants.py
 - src/api/routers/turns.py
Depends On:
 - enum
Notes:
 - Entitlements are evaluated server-side and default to fail-closed behavior.
"""

from __future__ import annotations

from enum import Enum


class EntitlementTier(str, Enum):
    FOUNDATION = "foundation"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class EntitledFeature(str, Enum):
    GOVERNANCE_INGRESS_BASELINE = "governance.ingress.baseline"
    GOVERNANCE_INGRESS_PROFILE = "governance.ingress.profile"
    GOVERNANCE_INGRESS_CUSTOM_RULES = "governance.ingress.custom_rules"
    GOVERNANCE_INGRESS_SIGNED_PLUGINS = "governance.ingress.signed_plugins"


_TIER_ORDER: dict[EntitlementTier, int] = {
    EntitlementTier.FOUNDATION: 0,
    EntitlementTier.PRO: 1,
    EntitlementTier.ENTERPRISE: 2,
}


_FEATURE_MIN_TIER: dict[EntitledFeature, EntitlementTier] = {
    EntitledFeature.GOVERNANCE_INGRESS_BASELINE: EntitlementTier.FOUNDATION,
    EntitledFeature.GOVERNANCE_INGRESS_PROFILE: EntitlementTier.PRO,
    EntitledFeature.GOVERNANCE_INGRESS_CUSTOM_RULES: EntitlementTier.PRO,
    EntitledFeature.GOVERNANCE_INGRESS_SIGNED_PLUGINS: EntitlementTier.ENTERPRISE,
}


def min_tier_for_feature(feature: EntitledFeature) -> EntitlementTier:
    return _FEATURE_MIN_TIER[feature]


def tier_satisfies(required: EntitlementTier, current: EntitlementTier) -> bool:
    return _TIER_ORDER[current] >= _TIER_ORDER[required]


def resolve_tier_from_roles(roles: list[str]) -> EntitlementTier:
    normalized = {str(role).strip().lower() for role in roles if str(role).strip()}
    if normalized & {
        "enterprise",
        "entitlement_enterprise",
        "entitlement:enterprise",
        "tier_enterprise",
        "plan_enterprise",
    }:
        return EntitlementTier.ENTERPRISE
    if normalized & {
        "pro",
        "entitlement_pro",
        "entitlement:pro",
        "tier_pro",
        "plan_pro",
    }:
        return EntitlementTier.PRO
    return EntitlementTier.FOUNDATION
