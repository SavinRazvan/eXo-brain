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

from src.policies.ingress_profiles import (
    IngressClassifierSettings,
    IngressCustomRule,
    resolve_ingress_profile_settings,
    supported_ingress_profiles,
)


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
    assert resolved.classifier.mode == "off"
    assert resolved.classifier.threshold == 0.65
    assert resolved.classifier.model_version == "heuristic-ingress-v1"
    assert len(resolved.classifier.signals) >= 4
    assert resolved.signed_plugin is None
    assert resolved.custom_rules == ()


def test_resolve_ingress_profile_settings_rejects_unknown_profile() -> None:
    with pytest.raises(ValueError, match="INGRESS_PROFILE_UNSUPPORTED"):
        resolve_ingress_profile_settings({"ingress_profile": "unknown_profile"})


def test_resolve_ingress_profile_settings_accepts_reduced_max_input_within_baseline() -> None:
    resolved = resolve_ingress_profile_settings(
        {"ingress_profile": "baseline", "ingress_max_input_chars": 5000}
    )
    assert resolved.max_input_chars == 5000


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


def test_resolve_ingress_profile_settings_accepts_classifier_shadow_config() -> None:
    resolved = resolve_ingress_profile_settings(
        {
            "ingress_classifier_mode": "shadow",
            "ingress_classifier_threshold": 0.4,
            "ingress_classifier_model_version": "mini-classifier-v2",
            "ingress_classifier_signals": ["bypass safety", "reveal secrets"],
            "ingress_classifier_review_channel": "classifier-review",
        }
    )
    assert resolved.classifier.mode == "shadow"
    assert resolved.classifier.threshold == 0.4
    assert resolved.classifier.model_version == "mini-classifier-v2"
    assert resolved.classifier.signals == ("bypass safety", "reveal secrets")
    assert resolved.classifier.review_channel == "classifier-review"


def test_resolve_ingress_profile_settings_rejects_invalid_classifier_mode() -> None:
    with pytest.raises(ValueError, match="INGRESS_CLASSIFIER_MODE_INVALID"):
        resolve_ingress_profile_settings({"ingress_classifier_mode": "strictest"})


def test_resolve_ingress_profile_settings_rejects_invalid_classifier_threshold() -> None:
    with pytest.raises(ValueError, match="INGRESS_CLASSIFIER_THRESHOLD_INVALID"):
        resolve_ingress_profile_settings({"ingress_classifier_mode": "enforce", "ingress_classifier_threshold": 1.2})


def test_resolve_ingress_profile_settings_rejects_empty_classifier_signals() -> None:
    with pytest.raises(ValueError, match="INGRESS_CLASSIFIER_SIGNALS_INVALID"):
        resolve_ingress_profile_settings({"ingress_classifier_mode": "shadow", "ingress_classifier_signals": []})


def test_resolve_ingress_profile_settings_accepts_signed_plugin_reference() -> None:
    resolved = resolve_ingress_profile_settings(
        {
            "signed_gate_plugin_ref": "plugin://trusted/signed-v1",
        }
    )
    assert resolved.signed_plugin is not None
    assert resolved.signed_plugin.manifest.plugin_ref == "plugin://trusted/signed-v1"
    assert resolved.signed_plugin.manifest.sandbox_mode == "declarative_rules_only"
    assert len(resolved.signed_plugin.rules) >= 1


def test_resolve_ingress_profile_settings_rejects_unknown_signed_plugin_reference() -> None:
    with pytest.raises(ValueError, match="INGRESS_SIGNED_PLUGIN_UNKNOWN"):
        resolve_ingress_profile_settings({"signed_gate_plugin_ref": "plugin://trusted/does-not-exist"})


def test_ingress_classifier_enabled_only_for_shadow_and_enforce() -> None:
    assert IngressClassifierSettings(
        mode="off", threshold=0.5, model_version="m", signals=()
    ).enabled is False
    assert IngressClassifierSettings(
        mode="shadow", threshold=0.5, model_version="m", signals=("x",)
    ).enabled is True
    assert IngressClassifierSettings(
        mode="enforce", threshold=0.5, model_version="m", signals=("x",)
    ).enabled is True


def test_ingress_custom_rule_matches_contains_and_regex() -> None:
    rule_contains = IngressCustomRule(
        rule_id="c1",
        action="deny",
        match_type="contains_any",
        patterns=("Secret",),
        reason_code="R1",
        message="m",
        case_sensitive=False,
    )
    assert rule_contains.matches("my secret value") is True
    rule_cs = IngressCustomRule(
        rule_id="c2",
        action="deny",
        match_type="contains_any",
        patterns=("AbC",),
        reason_code="R1",
        message="m",
        case_sensitive=True,
    )
    assert rule_cs.matches("xxxAbCxxx") is True
    assert rule_cs.matches("xxxabcxxx") is False

    rule_rx = IngressCustomRule(
        rule_id="c3",
        action="deny",
        match_type="regex_any",
        patterns=(r"ab\d+",),
        reason_code="R1",
        message="m",
    )
    assert rule_rx.matches("xxab12yy") is True


def test_ingress_custom_rule_to_overlay_payload_roundtrip_keys() -> None:
    rule = IngressCustomRule(
        rule_id="r1",
        action="escalate",
        match_type="contains_any",
        patterns=("p1",),
        reason_code="RC",
        message="msg",
        case_sensitive=True,
        review_channel="chan",
    )
    payload = rule.to_overlay_payload()
    assert payload["rule_id"] == "r1"
    assert payload["patterns"] == ["p1"]
    assert payload["case_sensitive"] is True


def test_resolve_ingress_profile_default_alias_maps_to_baseline() -> None:
    resolved = resolve_ingress_profile_settings({"ingress_profile": "default"})
    assert resolved.profile_name == "baseline"


def test_resolve_rejects_invalid_max_input_chars_type() -> None:
    with pytest.raises(ValueError, match="INGRESS_PROFILE_MAX_INPUT_INVALID"):
        resolve_ingress_profile_settings({"ingress_max_input_chars": "8000"})


def test_resolve_rejects_non_positive_max_input_chars() -> None:
    with pytest.raises(ValueError, match="INGRESS_PROFILE_MAX_INPUT_INVALID"):
        resolve_ingress_profile_settings({"ingress_max_input_chars": 0})


def test_resolve_rejects_phrases_when_not_list() -> None:
    with pytest.raises(ValueError, match="INGRESS_PROFILE_PHRASES_INVALID"):
        resolve_ingress_profile_settings({"ingress_prompt_injection_phrases": "nope"})


def test_resolve_rejects_phrase_longer_than_160_chars() -> None:
    base = resolve_ingress_profile_settings({"ingress_profile": "baseline"})
    phrases = list(base.prompt_injection_phrases) + ["x" * 161]
    with pytest.raises(ValueError, match="INGRESS_PROFILE_PHRASES_INVALID"):
        resolve_ingress_profile_settings({"ingress_prompt_injection_phrases": phrases})


def test_resolve_deduplicates_custom_phrase_list() -> None:
    base = resolve_ingress_profile_settings({"ingress_profile": "baseline"})
    core = list(base.prompt_injection_phrases)
    resolved = resolve_ingress_profile_settings(
        {
            "ingress_prompt_injection_phrases": core + ["dup", "  DUP  ", "extra-phrase"],
        }
    )
    assert "dup" in resolved.prompt_injection_phrases
    assert resolved.prompt_injection_phrases.count("dup") == 1


def test_resolve_rejects_more_than_64_phrases() -> None:
    base = resolve_ingress_profile_settings({"ingress_profile": "baseline"})
    core = list(base.prompt_injection_phrases)
    extra = [f"extra-{i}" for i in range(70)]
    with pytest.raises(ValueError, match="INGRESS_PROFILE_PHRASES_INVALID"):
        resolve_ingress_profile_settings({"ingress_prompt_injection_phrases": core + extra})


def test_resolve_rejects_custom_rules_when_not_list() -> None:
    with pytest.raises(ValueError, match="INGRESS_CUSTOM_RULES_INVALID"):
        resolve_ingress_profile_settings({"ingress_custom_rules": {}})


def test_resolve_rejects_too_many_custom_rules() -> None:
    rules = [
        {
            "rule_id": f"r{i}",
            "action": "deny",
            "match_type": "contains_any",
            "patterns": ["x"],
        }
        for i in range(21)
    ]
    with pytest.raises(ValueError, match="INGRESS_CUSTOM_RULES_INVALID"):
        resolve_ingress_profile_settings({"ingress_custom_rules": rules})


def test_resolve_rejects_custom_rule_when_payload_not_object() -> None:
    with pytest.raises(ValueError, match="INGRESS_CUSTOM_RULES_INVALID"):
        resolve_ingress_profile_settings({"ingress_custom_rules": ["string"]})


def test_resolve_rejects_duplicate_custom_rule_ids() -> None:
    payload = {
        "ingress_custom_rules": [
            {
                "rule_id": "same",
                "action": "deny",
                "match_type": "contains_any",
                "patterns": ["a"],
            },
            {
                "rule_id": "same",
                "action": "deny",
                "match_type": "contains_any",
                "patterns": ["b"],
            },
        ]
    }
    with pytest.raises(ValueError, match="INGRESS_CUSTOM_RULES_INVALID"):
        resolve_ingress_profile_settings(payload)


def test_resolve_rejects_invalid_match_type() -> None:
    with pytest.raises(ValueError, match="INGRESS_CUSTOM_RULES_INVALID"):
        resolve_ingress_profile_settings(
            {
                "ingress_custom_rules": [
                    {
                        "rule_id": "x",
                        "action": "deny",
                        "match_type": "equals",
                        "patterns": ["a"],
                    }
                ]
            }
        )


def test_resolve_rejects_patterns_not_list() -> None:
    with pytest.raises(ValueError, match="INGRESS_CUSTOM_RULES_INVALID"):
        resolve_ingress_profile_settings(
            {
                "ingress_custom_rules": [
                    {
                        "rule_id": "x",
                        "action": "deny",
                        "match_type": "contains_any",
                        "patterns": "nope",
                    }
                ]
            }
        )


def test_resolve_rejects_overlong_pattern() -> None:
    with pytest.raises(ValueError, match="INGRESS_CUSTOM_RULES_INVALID"):
        resolve_ingress_profile_settings(
            {
                "ingress_custom_rules": [
                    {
                        "rule_id": "x",
                        "action": "deny",
                        "match_type": "contains_any",
                        "patterns": ["x" * 257],
                    }
                ]
            }
        )


def test_resolve_rejects_too_many_patterns_per_rule() -> None:
    patterns = [f"p{i}" for i in range(21)]
    with pytest.raises(ValueError, match="INGRESS_CUSTOM_RULES_INVALID"):
        resolve_ingress_profile_settings(
            {
                "ingress_custom_rules": [
                    {
                        "rule_id": "x",
                        "action": "deny",
                        "match_type": "contains_any",
                        "patterns": patterns,
                    }
                ]
            }
        )


def test_resolve_rejects_invalid_regex_in_custom_rule() -> None:
    with pytest.raises(ValueError, match="INGRESS_CUSTOM_RULE_REGEX_INVALID"):
        resolve_ingress_profile_settings(
            {
                "ingress_custom_rules": [
                    {
                        "rule_id": "x",
                        "action": "deny",
                        "match_type": "regex_any",
                        "patterns": ["("],
                    }
                ]
            }
        )


def test_resolve_custom_rule_defaults_reason_message_and_review_channel() -> None:
    resolved = resolve_ingress_profile_settings(
        {
            "ingress_custom_rules": [
                {
                    "rule_id": "my_rule-1",
                    "action": "deny",
                    "match_type": "contains_any",
                    "patterns": ["z"],
                    "reason_code": "",
                    "message": "",
                    "review_channel": "   ",
                }
            ]
        }
    )
    rule = resolved.custom_rules[0]
    assert rule.reason_code.startswith("INGRESS_CUSTOM_RULE_")
    assert "MY_RULE" in rule.reason_code
    assert "my_rule-1" in rule.message
    assert rule.review_channel == "security-review"


def test_resolve_classifier_mode_aliases() -> None:
    shadow = resolve_ingress_profile_settings({"ingress_classifier_mode": "monitor"})
    assert shadow.classifier.mode == "shadow"
    off = resolve_ingress_profile_settings({"ingress_classifier_mode": "disabled"})
    assert off.classifier.mode == "off"


def test_resolve_classifier_threshold_must_be_numeric() -> None:
    with pytest.raises(ValueError, match="INGRESS_CLASSIFIER_THRESHOLD_INVALID"):
        resolve_ingress_profile_settings({"ingress_classifier_threshold": "0.5"})


def test_resolve_classifier_model_version_empty_uses_default() -> None:
    resolved = resolve_ingress_profile_settings({"ingress_classifier_model_version": "  "})
    assert resolved.classifier.model_version == "heuristic-ingress-v1"


def test_resolve_classifier_model_version_length_cap() -> None:
    with pytest.raises(ValueError, match="INGRESS_CLASSIFIER_MODEL_VERSION_INVALID"):
        resolve_ingress_profile_settings({"ingress_classifier_model_version": "x" * 81})


def test_resolve_classifier_review_channel_length_cap() -> None:
    with pytest.raises(ValueError, match="INGRESS_CLASSIFIER_REVIEW_CHANNEL_INVALID"):
        resolve_ingress_profile_settings({"ingress_classifier_review_channel": "x" * 81})


def test_resolve_classifier_signals_must_be_list() -> None:
    with pytest.raises(ValueError, match="INGRESS_CLASSIFIER_SIGNALS_INVALID"):
        resolve_ingress_profile_settings({"ingress_classifier_signals": "nope"})


def test_resolve_classifier_signal_entry_too_long() -> None:
    with pytest.raises(ValueError, match="INGRESS_CLASSIFIER_SIGNALS_INVALID"):
        resolve_ingress_profile_settings({"ingress_classifier_signals": ["x" * 161]})


def test_resolve_classifier_signals_more_than_64() -> None:
    signals = [f"s{i}" for i in range(65)]
    with pytest.raises(ValueError, match="INGRESS_CLASSIFIER_SIGNALS_INVALID"):
        resolve_ingress_profile_settings({"ingress_classifier_signals": signals})


def test_resolve_external_classifier_endpoint_requires_https() -> None:
    with pytest.raises(ValueError, match="INGRESS_CLASSIFIER_EXTERNAL_ENDPOINT_INVALID"):
        resolve_ingress_profile_settings(
            {"ingress_classifier_external_endpoint": "http://example.com/hook"}
        )


def test_resolve_external_classifier_endpoint_length_cap() -> None:
    with pytest.raises(ValueError, match="INGRESS_CLASSIFIER_EXTERNAL_ENDPOINT_INVALID"):
        resolve_ingress_profile_settings(
            {"ingress_classifier_external_endpoint": "https://x.example/" + "a" * 500}
        )


def test_resolve_external_classifier_timeout_must_be_int() -> None:
    with pytest.raises(ValueError, match="INGRESS_CLASSIFIER_EXTERNAL_TIMEOUT_INVALID"):
        resolve_ingress_profile_settings({"ingress_classifier_external_timeout_ms": 1000.0})


def test_resolve_external_classifier_timeout_range() -> None:
    with pytest.raises(ValueError, match="INGRESS_CLASSIFIER_EXTERNAL_TIMEOUT_INVALID"):
        resolve_ingress_profile_settings({"ingress_classifier_external_timeout_ms": 50})


def test_profile_resolution_to_overlay_and_audit_payload_shape() -> None:
    resolved = resolve_ingress_profile_settings(
        {
            "ingress_profile": "baseline",
            "signed_gate_plugin_ref": "plugin://trusted/signed-v1",
            "ingress_custom_rules": [
                {
                    "rule_id": "r1",
                    "action": "deny",
                    "match_type": "contains_any",
                    "patterns": ["x"],
                }
            ],
        }
    )
    patch = resolved.to_overlay_patch()
    assert patch["ingress_profile"] == "baseline"
    assert patch["signed_gate_plugin_ref"] == "plugin://trusted/signed-v1"
    assert len(patch["ingress_custom_rules"]) == 1

    audit = resolved.to_audit_payload()
    assert audit["ingress_custom_rule_ids"] == ["r1"]
    assert audit["signed_gate_plugin_rule_count"] >= 1


def test_resolve_phrases_skips_blank_entries_but_keeps_baseline() -> None:
    base = resolve_ingress_profile_settings({"ingress_profile": "baseline"})
    core = list(base.prompt_injection_phrases)
    resolved = resolve_ingress_profile_settings(
        {"ingress_prompt_injection_phrases": core + ["", "  ", "extra-unique-phrase"]}
    )
    assert "extra-unique-phrase" in resolved.prompt_injection_phrases


def test_resolve_phrases_rejects_when_all_entries_blank() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        resolve_ingress_profile_settings({"ingress_prompt_injection_phrases": ["", "  "]})

    with pytest.raises(ValueError, match="cannot be empty"):
        resolve_ingress_profile_settings({"ingress_prompt_injection_phrases": []})


def test_resolve_phrases_skips_duplicate_normalized_entries() -> None:
    base = resolve_ingress_profile_settings({"ingress_profile": "baseline"})
    core = list(base.prompt_injection_phrases)
    resolved = resolve_ingress_profile_settings(
        {"ingress_prompt_injection_phrases": core + ["dup-phrase", "  DUP-PHRASE  "]}
    )
    assert resolved.prompt_injection_phrases.count("dup-phrase") == 1


def test_resolve_custom_rules_rejects_blank_rule_id() -> None:
    with pytest.raises(ValueError, match="non-empty rule_id"):
        resolve_ingress_profile_settings(
            {
                "ingress_custom_rules": [
                    {
                        "rule_id": "  ",
                        "action": "deny",
                        "match_type": "contains_any",
                        "patterns": ["x"],
                    }
                ]
            }
        )


def test_resolve_custom_rules_rejects_when_patterns_all_blank() -> None:
    with pytest.raises(ValueError, match="at least one pattern"):
        resolve_ingress_profile_settings(
            {
                "ingress_custom_rules": [
                    {
                        "rule_id": "r1",
                        "action": "deny",
                        "match_type": "contains_any",
                        "patterns": ["", "  "],
                    }
                ]
            }
        )


def test_resolve_classifier_blank_review_channel_defaults() -> None:
    resolved = resolve_ingress_profile_settings({"ingress_classifier_review_channel": ""})
    assert resolved.classifier.review_channel == "security-review"


def test_resolve_classifier_signals_skip_blank_and_duplicate() -> None:
    resolved = resolve_ingress_profile_settings(
        {
            "ingress_classifier_signals": ["alpha", "", "  ", "alpha", "beta"],
        }
    )
    assert resolved.classifier.signals.count("alpha") == 1
    assert "beta" in resolved.classifier.signals


def test_default_custom_rule_reason_code_uses_rule_when_id_is_non_alnum_only() -> None:
    resolved = resolve_ingress_profile_settings(
        {
            "ingress_custom_rules": [
                {
                    "rule_id": "@@@",
                    "action": "deny",
                    "match_type": "contains_any",
                    "patterns": ["z"],
                }
            ]
        }
    )
    assert resolved.custom_rules[0].reason_code == "INGRESS_CUSTOM_RULE_RULE_DENY"
