"""
File: ingress_profiles.py
Path: src/policies/ingress_profiles.py
Role: Validate and normalize ingress profile/custom-rule policy overlays.
Used By:
 - src/api/routers/tenants.py
 - src/policies/ingress_gates.py
Depends On:
 - dataclasses
 - re
 - typing
Notes:
 - Compatibility controls prevent tenant overlays from weakening baseline trust guarantees.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Mapping


_BASELINE_PROMPT_INJECTION_PHRASES: tuple[str, ...] = (
    "ignore previous instructions",
    "reveal system prompt",
    "developer instructions",
    "jailbreak",
)


_INGRESS_PROFILE_BASELINES: dict[str, dict[str, Any]] = {
    "baseline": {
        "max_input_chars": 8000,
        "prompt_injection_phrases": _BASELINE_PROMPT_INJECTION_PHRASES,
    },
    "strict": {
        "max_input_chars": 4000,
        "prompt_injection_phrases": _BASELINE_PROMPT_INJECTION_PHRASES
        + (
            "disregard safety policy",
            "prompt leak",
        ),
    },
    "hardened": {
        "max_input_chars": 2000,
        "prompt_injection_phrases": _BASELINE_PROMPT_INJECTION_PHRASES
        + (
            "override compliance controls",
            "disable moderation",
            "simulate unrestricted mode",
        ),
    },
}


_PROFILE_ALIASES: dict[str, str] = {
    "default": "baseline",
}

_CLASSIFIER_MODE_ALIASES: dict[str, str] = {
    "disabled": "off",
    "none": "off",
    "monitor": "shadow",
}

_DEFAULT_CLASSIFIER_SIGNALS: tuple[str, ...] = (
    "ignore previous instructions",
    "reveal system prompt",
    "developer instructions",
    "jailbreak",
    "bypass safety",
    "disable moderation",
    "exfiltrate data",
    "reveal secrets",
)


@dataclass(slots=True, frozen=True)
class IngressClassifierSettings:
    mode: str
    threshold: float
    model_version: str
    signals: tuple[str, ...]
    review_channel: str = "security-review"

    @property
    def enabled(self) -> bool:
        return self.mode in {"shadow", "enforce"}


@dataclass(slots=True, frozen=True)
class IngressCustomRule:
    rule_id: str
    action: str
    match_type: str
    patterns: tuple[str, ...]
    reason_code: str
    message: str
    case_sensitive: bool = False
    review_channel: str = "security-review"

    def matches(self, user_input: str) -> bool:
        normalized_input = str(user_input)
        haystack = normalized_input if self.case_sensitive else normalized_input.lower()
        for pattern in self.patterns:
            if self.match_type == "contains_any":
                needle = pattern if self.case_sensitive else pattern.lower()
                if needle and needle in haystack:
                    return True
                continue
            flags = 0 if self.case_sensitive else re.IGNORECASE
            if re.search(pattern, normalized_input, flags=flags):
                return True
        return False

    def to_overlay_payload(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "action": self.action,
            "match_type": self.match_type,
            "patterns": list(self.patterns),
            "reason_code": self.reason_code,
            "message": self.message,
            "case_sensitive": self.case_sensitive,
            "review_channel": self.review_channel,
        }


@dataclass(slots=True, frozen=True)
class IngressProfileResolution:
    profile_name: str
    max_input_chars: int
    prompt_injection_phrases: tuple[str, ...]
    classifier: IngressClassifierSettings
    custom_rules: tuple[IngressCustomRule, ...] = field(default_factory=tuple)
    compatibility_mode: str = "strict"

    def to_overlay_patch(self) -> dict[str, Any]:
        return {
            "ingress_profile": self.profile_name,
            "ingress_max_input_chars": self.max_input_chars,
            "ingress_prompt_injection_phrases": list(self.prompt_injection_phrases),
            "ingress_custom_rules": [rule.to_overlay_payload() for rule in self.custom_rules],
            "ingress_classifier_mode": self.classifier.mode,
            "ingress_classifier_threshold": self.classifier.threshold,
            "ingress_classifier_model_version": self.classifier.model_version,
            "ingress_classifier_signals": list(self.classifier.signals),
            "ingress_classifier_review_channel": self.classifier.review_channel,
            "ingress_profile_compatibility_mode": self.compatibility_mode,
        }

    def to_audit_payload(self) -> dict[str, Any]:
        return {
            "ingress_profile": self.profile_name,
            "ingress_max_input_chars": self.max_input_chars,
            "ingress_prompt_injection_phrase_count": len(self.prompt_injection_phrases),
            "ingress_custom_rule_count": len(self.custom_rules),
            "ingress_custom_rule_ids": [rule.rule_id for rule in self.custom_rules],
            "ingress_classifier_mode": self.classifier.mode,
            "ingress_classifier_threshold": self.classifier.threshold,
            "ingress_classifier_model_version": self.classifier.model_version,
            "ingress_classifier_signal_count": len(self.classifier.signals),
            "ingress_classifier_review_channel": self.classifier.review_channel,
            "ingress_profile_compatibility_mode": self.compatibility_mode,
        }


def supported_ingress_profiles() -> tuple[str, ...]:
    return tuple(sorted(_INGRESS_PROFILE_BASELINES.keys()))


def resolve_ingress_profile_settings(overlay: Mapping[str, Any]) -> IngressProfileResolution:
    profile_name = _normalize_profile_name(overlay.get("ingress_profile"))
    baseline = _INGRESS_PROFILE_BASELINES[profile_name]
    baseline_max_chars = int(baseline["max_input_chars"])
    baseline_phrases = tuple(str(item).strip().lower() for item in baseline["prompt_injection_phrases"])
    max_input_chars = _resolve_max_input_chars(overlay.get("ingress_max_input_chars"), baseline_max_chars)
    prompt_injection_phrases = _resolve_prompt_injection_phrases(
        overlay.get("ingress_prompt_injection_phrases"),
        baseline_phrases,
    )
    classifier = _resolve_classifier_settings(overlay)
    custom_rules = _resolve_custom_rules(overlay.get("ingress_custom_rules"))
    return IngressProfileResolution(
        profile_name=profile_name,
        max_input_chars=max_input_chars,
        prompt_injection_phrases=prompt_injection_phrases,
        classifier=classifier,
        custom_rules=custom_rules,
    )


def _normalize_profile_name(raw_profile: Any) -> str:
    normalized = str(raw_profile or "baseline").strip().lower()
    normalized = _PROFILE_ALIASES.get(normalized, normalized)
    if normalized in _INGRESS_PROFILE_BASELINES:
        return normalized
    allowed = ", ".join(supported_ingress_profiles())
    raise ValueError(
        f"INGRESS_PROFILE_UNSUPPORTED: ingress_profile must be one of [{allowed}], got '{normalized}'."
    )


def _resolve_max_input_chars(raw_value: Any, baseline_max_chars: int) -> int:
    if raw_value is None:
        return baseline_max_chars
    if not isinstance(raw_value, int) or raw_value <= 0:
        raise ValueError(
            "INGRESS_PROFILE_MAX_INPUT_INVALID: ingress_max_input_chars must be a positive integer."
        )
    if raw_value > baseline_max_chars:
        raise ValueError(
            "INGRESS_PROFILE_COMPATIBILITY_MAX_INPUT_RELAXATION_NOT_ALLOWED: "
            "ingress_max_input_chars cannot exceed the selected ingress profile baseline."
        )
    return raw_value


def _resolve_prompt_injection_phrases(
    raw_phrases: Any,
    baseline_phrases: tuple[str, ...],
) -> tuple[str, ...]:
    if raw_phrases is None:
        return baseline_phrases
    if not isinstance(raw_phrases, list):
        raise ValueError(
            "INGRESS_PROFILE_PHRASES_INVALID: ingress_prompt_injection_phrases must be a list of strings."
        )
    normalized: list[str] = []
    seen: set[str] = set()
    for phrase in raw_phrases:
        phrase_value = str(phrase).strip().lower()
        if not phrase_value:
            continue
        if len(phrase_value) > 160:
            raise ValueError(
                "INGRESS_PROFILE_PHRASES_INVALID: phrase entries must be <=160 characters."
            )
        if phrase_value in seen:
            continue
        seen.add(phrase_value)
        normalized.append(phrase_value)
    if not normalized:
        raise ValueError(
            "INGRESS_PROFILE_PHRASES_INVALID: ingress_prompt_injection_phrases cannot be empty."
        )
    if not set(baseline_phrases).issubset(set(normalized)):
        raise ValueError(
            "INGRESS_PROFILE_COMPATIBILITY_BASELINE_PHRASES_REQUIRED: "
            "custom phrase lists must include baseline prompt-injection phrases."
        )
    if len(normalized) > 64:
        raise ValueError(
            "INGRESS_PROFILE_PHRASES_INVALID: ingress_prompt_injection_phrases supports at most 64 entries."
        )
    return tuple(normalized)


def _resolve_custom_rules(raw_rules: Any) -> tuple[IngressCustomRule, ...]:
    if raw_rules is None:
        return ()
    if not isinstance(raw_rules, list):
        raise ValueError("INGRESS_CUSTOM_RULES_INVALID: ingress_custom_rules must be a list.")
    if len(raw_rules) > 20:
        raise ValueError("INGRESS_CUSTOM_RULES_INVALID: at most 20 ingress_custom_rules are allowed.")
    rules: list[IngressCustomRule] = []
    seen_rule_ids: set[str] = set()
    for index, rule_payload in enumerate(raw_rules):
        if not isinstance(rule_payload, Mapping):
            raise ValueError(
                f"INGRESS_CUSTOM_RULES_INVALID: rule at index {index} must be an object."
            )
        rule_id = str(rule_payload.get("rule_id", "")).strip()
        if not rule_id:
            raise ValueError(
                f"INGRESS_CUSTOM_RULES_INVALID: rule at index {index} requires non-empty rule_id."
            )
        if rule_id in seen_rule_ids:
            raise ValueError(
                f"INGRESS_CUSTOM_RULES_INVALID: duplicate rule_id '{rule_id}' is not allowed."
            )
        seen_rule_ids.add(rule_id)
        action = str(rule_payload.get("action", "")).strip().lower()
        if action not in {"deny", "escalate"}:
            raise ValueError(
                f"INGRESS_CUSTOM_RULES_INVALID: rule '{rule_id}' action must be 'deny' or 'escalate'."
            )
        match_type = str(rule_payload.get("match_type", "")).strip().lower()
        if match_type not in {"contains_any", "regex_any"}:
            raise ValueError(
                "INGRESS_CUSTOM_RULES_INVALID: "
                f"rule '{rule_id}' match_type must be 'contains_any' or 'regex_any'."
            )
        raw_patterns = rule_payload.get("patterns")
        if not isinstance(raw_patterns, list):
            raise ValueError(
                f"INGRESS_CUSTOM_RULES_INVALID: rule '{rule_id}' patterns must be a list."
            )
        normalized_patterns: list[str] = []
        for pattern in raw_patterns:
            pattern_value = str(pattern).strip()
            if not pattern_value:
                continue
            if len(pattern_value) > 256:
                raise ValueError(
                    f"INGRESS_CUSTOM_RULES_INVALID: rule '{rule_id}' pattern entries must be <=256 characters."
                )
            normalized_patterns.append(pattern_value)
        if not normalized_patterns:
            raise ValueError(
                f"INGRESS_CUSTOM_RULES_INVALID: rule '{rule_id}' must include at least one pattern."
            )
        if len(normalized_patterns) > 20:
            raise ValueError(
                f"INGRESS_CUSTOM_RULES_INVALID: rule '{rule_id}' supports at most 20 patterns."
            )
        if match_type == "regex_any":
            _validate_regex_patterns(rule_id, normalized_patterns)
        reason_code = str(rule_payload.get("reason_code", "")).strip()
        if not reason_code:
            reason_code = _default_custom_rule_reason_code(rule_id, action)
        message = str(rule_payload.get("message", "")).strip()
        if not message:
            message = f"Ingress custom rule '{rule_id}' matched input content."
        case_sensitive = bool(rule_payload.get("case_sensitive", False))
        review_channel = str(rule_payload.get("review_channel", "security-review")).strip()
        if not review_channel:
            review_channel = "security-review"
        rules.append(
            IngressCustomRule(
                rule_id=rule_id,
                action=action,
                match_type=match_type,
                patterns=tuple(normalized_patterns),
                reason_code=reason_code,
                message=message,
                case_sensitive=case_sensitive,
                review_channel=review_channel,
            )
        )
    return tuple(rules)


def _resolve_classifier_settings(overlay: Mapping[str, Any]) -> IngressClassifierSettings:
    raw_mode = str(overlay.get("ingress_classifier_mode", "off")).strip().lower()
    mode = _CLASSIFIER_MODE_ALIASES.get(raw_mode, raw_mode)
    if mode not in {"off", "shadow", "enforce"}:
        raise ValueError(
            "INGRESS_CLASSIFIER_MODE_INVALID: ingress_classifier_mode must be one of "
            "['off', 'shadow', 'enforce']."
        )
    raw_threshold = overlay.get("ingress_classifier_threshold", 0.65)
    if not isinstance(raw_threshold, (int, float)):
        raise ValueError(
            "INGRESS_CLASSIFIER_THRESHOLD_INVALID: ingress_classifier_threshold must be a number in [0,1]."
        )
    threshold = float(raw_threshold)
    if threshold < 0.0 or threshold > 1.0:
        raise ValueError(
            "INGRESS_CLASSIFIER_THRESHOLD_INVALID: ingress_classifier_threshold must be in [0,1]."
        )
    raw_model_version = str(overlay.get("ingress_classifier_model_version", "heuristic-ingress-v1")).strip()
    model_version = raw_model_version or "heuristic-ingress-v1"
    if len(model_version) > 80:
        raise ValueError(
            "INGRESS_CLASSIFIER_MODEL_VERSION_INVALID: ingress_classifier_model_version must be <=80 chars."
        )
    review_channel = str(overlay.get("ingress_classifier_review_channel", "security-review")).strip()
    if not review_channel:
        review_channel = "security-review"
    if len(review_channel) > 80:
        raise ValueError(
            "INGRESS_CLASSIFIER_REVIEW_CHANNEL_INVALID: ingress_classifier_review_channel must be <=80 chars."
        )
    signals = _resolve_classifier_signals(overlay.get("ingress_classifier_signals"))
    return IngressClassifierSettings(
        mode=mode,
        threshold=threshold,
        model_version=model_version,
        signals=signals,
        review_channel=review_channel,
    )


def _resolve_classifier_signals(raw_signals: Any) -> tuple[str, ...]:
    if raw_signals is None:
        return _DEFAULT_CLASSIFIER_SIGNALS
    if not isinstance(raw_signals, list):
        raise ValueError("INGRESS_CLASSIFIER_SIGNALS_INVALID: ingress_classifier_signals must be a list.")
    normalized: list[str] = []
    seen: set[str] = set()
    for signal in raw_signals:
        signal_value = str(signal).strip().lower()
        if not signal_value:
            continue
        if len(signal_value) > 160:
            raise ValueError(
                "INGRESS_CLASSIFIER_SIGNALS_INVALID: signal entries must be <=160 characters."
            )
        if signal_value in seen:
            continue
        seen.add(signal_value)
        normalized.append(signal_value)
    if not normalized:
        raise ValueError(
            "INGRESS_CLASSIFIER_SIGNALS_INVALID: ingress_classifier_signals cannot be empty."
        )
    if len(normalized) > 64:
        raise ValueError(
            "INGRESS_CLASSIFIER_SIGNALS_INVALID: ingress_classifier_signals supports at most 64 entries."
        )
    return tuple(normalized)


def _validate_regex_patterns(rule_id: str, patterns: list[str]) -> None:
    for pattern in patterns:
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ValueError(
                "INGRESS_CUSTOM_RULE_REGEX_INVALID: "
                f"rule '{rule_id}' contains invalid regex pattern '{pattern}'."
            ) from exc


def _default_custom_rule_reason_code(rule_id: str, action: str) -> str:
    fragment = "".join(ch if ch.isalnum() else "_" for ch in rule_id.upper())
    fragment = "_".join(part for part in fragment.split("_") if part)
    if not fragment:
        fragment = "RULE"
    return f"INGRESS_CUSTOM_RULE_{fragment[:48]}_{action.upper()}"
