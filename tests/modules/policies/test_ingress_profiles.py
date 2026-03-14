"""
File: test_ingress_profiles.py
Path: tests/modules/policies/test_ingress_profiles.py
Role: Unit tests for ingress profile and custom-rule overlay validation.
Used By:
 - pytest
Depends On:
 - src/policies/ingress_profiles.py
Notes:
 - Verifies compatibility controls that prevent profile weakening.
"""

from __future__ import annotations

import pytest

from src.policies.ingress_profiles import resolve_ingress_profile_settings, supported_ingress_profiles


def test_supported_ingress_profiles_exposes_expected_profiles() -> None:
    profiles = supported_ingress_profiles()
    assert "baseline" in profiles
    assert "strict" in profiles
    assert "hardened" in profiles


def test_resolve_ingress_profile_settings_returns_baseline_defaults() -> None:
    resolved = resolve_ingress_profile_settings({})
    assert resolved.profile_name == "baseline"
    assert resolved.max_input_chars == 8000
    assert len(resolved.prompt_injection_phrases) >= 4
    assert resolved.custom_rules == ()


def test_resolve_ingress_profile_settings_rejects_unknown_profile() -> None:
    with pytest.raises(ValueError, match="INGRESS_PROFILE_UNSUPPORTED"):
        resolve_ingress_profile_settings({"ingress_profile": "unknown_profile"})


def test_resolve_ingress_profile_settings_rejects_max_chars_relaxation() -> None:
    with pytest.raises(ValueError, match="INGRESS_PROFILE_COMPATIBILITY_MAX_INPUT_RELAXATION_NOT_ALLOWED"):
        resolve_ingress_profile_settings(
            {
                "ingress_profile": "strict",
                "ingress_max_input_chars": 8001,
            }
        )


def test_resolve_ingress_profile_settings_rejects_phrase_set_without_baseline_entries() -> None:
    with pytest.raises(ValueError, match="INGRESS_PROFILE_COMPATIBILITY_BASELINE_PHRASES_REQUIRED"):
        resolve_ingress_profile_settings(
            {
                "ingress_profile": "strict",
                "ingress_prompt_injection_phrases": ["custom phrase only"],
            }
        )


def test_resolve_ingress_profile_settings_accepts_valid_custom_rules() -> None:
    resolved = resolve_ingress_profile_settings(
        {
            "ingress_profile": "baseline",
            "ingress_custom_rules": [
                {
                    "rule_id": "deny-sensitive-share",
                    "action": "deny",
                    "match_type": "contains_any",
                    "patterns": ["share access token"],
                    "reason_code": "INGRESS_DENY_SENSITIVE_SHARE",
                    "message": "Sensitive token sharing is denied.",
                },
                {
                    "rule_id": "escalate-prod-secrets",
                    "action": "escalate",
                    "match_type": "regex_any",
                    "patterns": [r"prod-secret-[0-9]+"],
                },
            ],
        }
    )
    assert len(resolved.custom_rules) == 2
    assert resolved.custom_rules[0].action == "deny"
    assert resolved.custom_rules[1].action == "escalate"


def test_resolve_ingress_profile_settings_rejects_invalid_custom_rule_action() -> None:
    with pytest.raises(ValueError, match="INGRESS_CUSTOM_RULES_INVALID"):
        resolve_ingress_profile_settings(
            {
                "ingress_custom_rules": [
                    {
                        "rule_id": "allow-rule-not-supported",
                        "action": "allow",
                        "match_type": "contains_any",
                        "patterns": ["anything"],
                    }
                ]
            }
        )
