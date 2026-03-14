"""
File: policy_templates.py
Path: src/policies/policy_templates.py
Role: Packaged governance policy-template registry and overlay compiler.
Used By:
 - src/api/routers/tenants.py
 - tests/modules/policies/test_policy_templates.py
Depends On:
 - dataclasses
 - copy
 - typing
 - src/policies/ingress_profiles.py
Notes:
 - Templates compile into the standard tenant policy overlay format.
 - Template application is deterministic and does not bypass ingress profile validation.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping

from src.policies.ingress_profiles import IngressProfileResolution, resolve_ingress_profile_settings

_LOCKED_TEMPLATE_KEYS: tuple[str, ...] = (
    "ingress_profile",
    "ingress_max_input_chars",
    "ingress_prompt_injection_phrases",
    "ingress_custom_rules",
    "ingress_classifier_mode",
    "ingress_classifier_threshold",
    "ingress_classifier_model_version",
    "ingress_classifier_signals",
    "ingress_classifier_review_channel",
    "signed_gate_plugin_ref",
    "signed_gate_plugin_version",
    "signed_gate_plugin_signer",
    "signed_gate_plugin_signature_sha256",
    "signed_gate_plugin_sandbox_mode",
    "ingress_profile_compatibility_mode",
)


@dataclass(slots=True, frozen=True)
class PolicyTemplateDefinition:
    template_id: str
    packaged_risk_profile_id: str
    title: str
    description: str
    minimum_tier: str
    overlay: Mapping[str, Any]


def list_policy_templates() -> tuple[PolicyTemplateDefinition, ...]:
    return tuple(
        _POLICY_TEMPLATE_REGISTRY[key]
        for key in sorted(_POLICY_TEMPLATE_REGISTRY.keys())
    )


def resolve_policy_template(template_id: str) -> PolicyTemplateDefinition:
    normalized = str(template_id).strip()
    if not normalized:
        raise ValueError("POLICY_TEMPLATE_REF_INVALID: template_id cannot be empty.")
    template = _POLICY_TEMPLATE_REGISTRY.get(normalized)
    if template is not None:
        return template
    allowed = ", ".join(sorted(_POLICY_TEMPLATE_REGISTRY.keys()))
    raise ValueError(
        "POLICY_TEMPLATE_UNKNOWN: "
        f"unknown template_id '{normalized}'. Allowed template IDs: [{allowed}]."
    )


def policy_template_summary_payload(template: PolicyTemplateDefinition) -> dict[str, Any]:
    resolution = resolve_ingress_profile_settings(template.overlay)
    return {
        "template_id": template.template_id,
        "packaged_risk_profile_id": template.packaged_risk_profile_id,
        "title": template.title,
        "description": template.description,
        "minimum_tier": template.minimum_tier,
        "ingress_profile": resolution.profile_name,
        "ingress_classifier_mode": resolution.classifier.mode,
        "ingress_custom_rule_count": len(resolution.custom_rules),
        "includes_signed_plugin": resolution.signed_plugin is not None,
    }


def compile_policy_template_overlay(
    template_id: str,
    *,
    merge_with_overlay: Mapping[str, Any] | None = None,
    overlay_extra: Mapping[str, Any] | None = None,
) -> tuple[PolicyTemplateDefinition, dict[str, Any], IngressProfileResolution]:
    template = resolve_policy_template(template_id)
    compiled_overlay: dict[str, Any] = {}
    if merge_with_overlay:
        compiled_overlay.update(_normalize_overlay_fragment(merge_with_overlay))
        for key in _LOCKED_TEMPLATE_KEYS:
            compiled_overlay.pop(key, None)
    compiled_overlay.update(_normalize_overlay_fragment(template.overlay))
    extra_fragment = _normalize_overlay_fragment(overlay_extra or {})
    _validate_template_extra_keys(extra_fragment)
    compiled_overlay.update(extra_fragment)
    compiled_overlay.setdefault("deny_tools", [])
    compiled_overlay.setdefault("escalate_risk_tiers", [])
    compiled_overlay.setdefault("escalate_state_changing", False)
    ingress_resolution = resolve_ingress_profile_settings(compiled_overlay)
    compiled_overlay.update(ingress_resolution.to_overlay_patch())
    return template, compiled_overlay, ingress_resolution


def _normalize_overlay_fragment(fragment: Mapping[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(dict(fragment))
    deny_tools = normalized.get("deny_tools")
    if isinstance(deny_tools, tuple):
        normalized["deny_tools"] = list(deny_tools)
    escalate_risk_tiers = normalized.get("escalate_risk_tiers")
    if isinstance(escalate_risk_tiers, tuple):
        normalized["escalate_risk_tiers"] = list(escalate_risk_tiers)
    if "escalate_state_changing" in normalized:
        normalized["escalate_state_changing"] = bool(normalized["escalate_state_changing"])
    return normalized


def _validate_template_extra_keys(extra_fragment: Mapping[str, Any]) -> None:
    if not extra_fragment:
        return
    locked = sorted(key for key in extra_fragment.keys() if key in _LOCKED_TEMPLATE_KEYS)
    if not locked:
        return
    blocked = ", ".join(locked)
    raise ValueError(
        "POLICY_TEMPLATE_EXTRA_LOCKED_FIELDS: "
        f"extra cannot override template-governed ingress fields [{blocked}]."
    )


_POLICY_TEMPLATES: tuple[PolicyTemplateDefinition, ...] = (
    PolicyTemplateDefinition(
        template_id="template://governance/protocol-guard-v1",
        packaged_risk_profile_id="risk://packaged/protocol-guard-v1",
        title="Protocol Guard",
        description=(
            "Strict protocol-integrity profile with classifier shadow telemetry and "
            "escalation on policy-bypass intent."
        ),
        minimum_tier="pro",
        overlay={
            "deny_tools": [],
            "escalate_risk_tiers": ["HIGH"],
            "escalate_state_changing": True,
            "ingress_profile": "strict",
            "ingress_custom_rules": [
                {
                    "rule_id": "template-protocol-bypass-escalate",
                    "action": "escalate",
                    "match_type": "regex_any",
                    "patterns": [r"(?:ignore|bypass|override)\s+(?:protocol|policy|guardrail)s?"],
                    "reason_code": "INGRESS_TEMPLATE_PROTOCOL_BYPASS_ESCALATE",
                    "message": "Protocol-guard template escalated potential policy-bypass phrasing.",
                }
            ],
            "ingress_classifier_mode": "shadow",
            "ingress_classifier_threshold": 0.35,
            "ingress_classifier_model_version": "template-protocol-guard-v1",
            "ingress_classifier_signals": [
                "ignore protocol",
                "bypass policy",
                "skip guardrails",
                "disable moderation",
            ],
            "ingress_classifier_review_channel": "security-review",
        },
    ),
    PolicyTemplateDefinition(
        template_id="template://governance/data-perimeter-v1",
        packaged_risk_profile_id="risk://packaged/data-perimeter-v1",
        title="Data Perimeter",
        description=(
            "Hardened data-protection profile with classifier enforce mode and "
            "packaged deny/escalate rules for secret export prompts."
        ),
        minimum_tier="pro",
        overlay={
            "deny_tools": ["delete_records"],
            "escalate_risk_tiers": ["MEDIUM", "HIGH"],
            "escalate_state_changing": True,
            "ingress_profile": "hardened",
            "ingress_custom_rules": [
                {
                    "rule_id": "template-deny-secret-export",
                    "action": "deny",
                    "match_type": "contains_any",
                    "patterns": [
                        "export secrets",
                        "dump credentials",
                        "reveal private key",
                    ],
                    "reason_code": "INGRESS_TEMPLATE_DENY_SECRET_EXPORT",
                    "message": "Data-perimeter template denied explicit secret-export request.",
                },
                {
                    "rule_id": "template-escalate-tenant-data-exfil",
                    "action": "escalate",
                    "match_type": "regex_any",
                    "patterns": [
                        r"(?:exfiltrate|extract)\s+(?:tenant|customer|internal)\s+data",
                    ],
                    "reason_code": "INGRESS_TEMPLATE_ESCALATE_DATA_EXFIL",
                    "message": "Data-perimeter template escalated potential data-exfiltration intent.",
                },
            ],
            "ingress_classifier_mode": "enforce",
            "ingress_classifier_threshold": 0.28,
            "ingress_classifier_model_version": "template-data-perimeter-v1",
            "ingress_classifier_signals": [
                "export secrets",
                "dump credentials",
                "extract customer data",
                "bypass compliance controls",
            ],
            "ingress_classifier_review_channel": "security-review",
        },
    ),
)

_POLICY_TEMPLATE_REGISTRY: dict[str, PolicyTemplateDefinition] = {
    template.template_id: template for template in _POLICY_TEMPLATES
}

