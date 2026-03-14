"""
File: entitlements.py
Path: src/api/middleware/entitlements.py
Role: Evaluate and normalize entitlement decisions at API governance surfaces.
Used By:
 - src/api/routers/tenants.py
 - src/api/routers/turns.py
Depends On:
 - src/identity/contracts.py
 - src/policies/entitlements.py
 - src/schemas/tool_io.py
Notes:
 - Entitlement decisions are explicit allow/deny records with reason codes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from src.identity.contracts import IdentityContext
from src.policies.entitlements import (
    EntitledFeature,
    EntitlementTier,
    min_tier_for_feature,
    resolve_tier_from_roles,
    tier_satisfies,
)
from src.schemas.tool_io import PolicyAction


@dataclass(slots=True)
class EntitlementDecision:
    schema_version: str
    decision: PolicyAction
    reason_code: str
    message: str
    feature: EntitledFeature
    required_tier: EntitlementTier
    current_tier: EntitlementTier

    def to_payload(self) -> dict[str, str]:
        return {
            "schema_version": self.schema_version,
            "decision": self.decision.value,
            "reason_code": self.reason_code,
            "message": self.message,
            "feature": self.feature.value,
            "required_tier": self.required_tier.value,
            "current_tier": self.current_tier.value,
        }


def evaluate_feature_entitlement(
    *,
    identity: IdentityContext,
    feature: EntitledFeature,
) -> EntitlementDecision:
    required_tier = min_tier_for_feature(feature)
    current_tier = resolve_tier_from_roles(list(identity.roles))
    if tier_satisfies(required_tier, current_tier):
        return EntitlementDecision(
            schema_version="1.0",
            decision=PolicyAction.ALLOW,
            reason_code="ENTITLEMENT_ALLOWED",
            message="Entitlement requirements satisfied for requested governance feature.",
            feature=feature,
            required_tier=required_tier,
            current_tier=current_tier,
        )
    return EntitlementDecision(
        schema_version="1.0",
        decision=PolicyAction.DENY,
        reason_code="ENTITLEMENT_TIER_REQUIRED",
        message=(
            f"Feature '{feature.value}' requires tier '{required_tier.value}' "
            f"but caller tier is '{current_tier.value}'."
        ),
        feature=feature,
        required_tier=required_tier,
        current_tier=current_tier,
    )


async def emit_entitlement_decision_event(
    *,
    audit_pipeline: Any,
    correlation_id: str,
    tenant_id: str,
    surface: str,
    route: str,
    decision: EntitlementDecision,
    extra_payload: Mapping[str, Any] | None = None,
) -> None:
    if audit_pipeline is None:
        return
    payload: dict[str, Any] = {
        "surface": surface,
        "route": route,
        **decision.to_payload(),
    }
    if extra_payload:
        payload.update(dict(extra_payload))
    await audit_pipeline.emit(
        event_type="entitlement_decision",
        correlation_id=correlation_id,
        tenant_id=tenant_id,
        payload=payload,
    )


def required_feature_for_governance_overlay(overlay: Mapping[str, Any]) -> EntitledFeature:
    signed_plugin_ref = str(overlay.get("signed_gate_plugin_ref", "")).strip()
    if signed_plugin_ref:
        return EntitledFeature.GOVERNANCE_INGRESS_SIGNED_PLUGINS

    custom_rules = overlay.get("ingress_custom_rules")
    if isinstance(custom_rules, (list, dict)) and len(custom_rules) > 0:
        return EntitledFeature.GOVERNANCE_INGRESS_CUSTOM_RULES

    ingress_profile = str(overlay.get("ingress_profile", "")).strip().lower()
    if ingress_profile and ingress_profile not in {"baseline", "default"}:
        return EntitledFeature.GOVERNANCE_INGRESS_PROFILE

    max_chars = overlay.get("ingress_max_input_chars")
    if isinstance(max_chars, int) and max_chars > 0:
        return EntitledFeature.GOVERNANCE_INGRESS_PROFILE

    phrases = overlay.get("ingress_prompt_injection_phrases")
    if isinstance(phrases, list) and len(phrases) > 0:
        return EntitledFeature.GOVERNANCE_INGRESS_PROFILE

    return EntitledFeature.GOVERNANCE_INGRESS_BASELINE
