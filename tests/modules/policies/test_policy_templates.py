"""
File: test_policy_templates.py
Path: tests/modules/policies/test_policy_templates.py
Role: Unit tests for packaged policy-template registry and overlay compiler contracts.
Used By:
 - pytest
Depends On:
 - src/policies/policy_templates.py
Notes:
 - Ensures packaged profiles compile through existing ingress validation contracts.
"""

from __future__ import annotations

import pytest

from src.policies.policy_templates import (
    compile_policy_template_overlay,
    list_policy_templates,
    policy_template_summary_payload,
    resolve_policy_template,
)


def test_list_policy_templates_exposes_packaged_profiles() -> None:
    templates = list_policy_templates()
    template_ids = {template.template_id for template in templates}
    assert "template://governance/protocol-guard-v1" in template_ids
    assert "template://governance/data-perimeter-v1" in template_ids


def test_resolve_policy_template_rejects_unknown_template() -> None:
    with pytest.raises(ValueError, match="POLICY_TEMPLATE_UNKNOWN"):
        resolve_policy_template("template://governance/unknown")


def test_policy_template_summary_payload_reports_compiled_metadata() -> None:
    template = resolve_policy_template("template://governance/protocol-guard-v1")
    summary = policy_template_summary_payload(template)
    assert summary["minimum_tier"] == "pro"
    assert summary["ingress_profile"] == "strict"
    assert summary["ingress_classifier_mode"] == "shadow"
    assert summary["includes_signed_plugin"] is False


def test_compile_policy_template_overlay_returns_normalized_overlay_patch() -> None:
    template, overlay, ingress_resolution = compile_policy_template_overlay(
        "template://governance/data-perimeter-v1"
    )
    assert template.packaged_risk_profile_id == "risk://packaged/data-perimeter-v1"
    assert ingress_resolution.profile_name == "hardened"
    assert overlay["ingress_profile"] == "hardened"
    assert overlay["ingress_classifier_mode"] == "enforce"
    assert overlay["ingress_profile_compatibility_mode"] == "strict"
    assert len(overlay["ingress_custom_rules"]) >= 2


def test_compile_policy_template_overlay_rejects_locked_extra_overrides() -> None:
    with pytest.raises(ValueError, match="POLICY_TEMPLATE_EXTRA_LOCKED_FIELDS"):
        compile_policy_template_overlay(
            "template://governance/protocol-guard-v1",
            overlay_extra={"ingress_profile": "baseline"},
        )


def test_compile_policy_template_overlay_merge_mode_preserves_non_template_keys() -> None:
    _, overlay, _ = compile_policy_template_overlay(
        "template://governance/protocol-guard-v1",
        merge_with_overlay={
            "custom_flag": True,
            "deny_tools": ["legacy_tool"],
        },
        overlay_extra={"ops_owner": "security-team"},
    )
    assert overlay["custom_flag"] is True
    assert overlay["ops_owner"] == "security-team"
    assert overlay["ingress_profile"] == "strict"
    assert overlay["escalate_state_changing"] is True

