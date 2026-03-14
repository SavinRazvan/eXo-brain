"""
File: ingress_signed_plugins.py
Path: src/policies/ingress_signed_plugins.py
Role: Signed ingress plugin contracts, validation, and lifecycle transition guards.
Used By:
 - src/policies/ingress_profiles.py
 - src/api/routers/tenants.py
 - src/policies/ingress_gates.py
Depends On:
 - dataclasses
 - hashlib
 - json
 - re
Notes:
 - Runtime plugin execution remains declarative-only (no dynamic code import/call).
 - Signature checks are deterministic and verifiable from manifest + rule payload.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import re
from typing import Any, Mapping

_SANDBOX_MODE_DECLARATIVE_ONLY = "declarative_rules_only"
_TRUSTED_SIGNERS: tuple[str, ...] = ("exo-security",)


@dataclass(slots=True, frozen=True)
class SignedIngressPluginRule:
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

    def to_payload(self) -> dict[str, Any]:
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
class SignedIngressPluginManifest:
    plugin_ref: str
    version: str
    compatible_core_major: int
    signer: str
    signature_sha256: str
    sandbox_mode: str = _SANDBOX_MODE_DECLARATIVE_ONLY


@dataclass(slots=True, frozen=True)
class SignedIngressPlugin:
    manifest: SignedIngressPluginManifest
    rules: tuple[SignedIngressPluginRule, ...]

    def to_audit_payload(self) -> dict[str, Any]:
        return {
            "signed_gate_plugin_ref": self.manifest.plugin_ref,
            "signed_gate_plugin_version": self.manifest.version,
            "signed_gate_plugin_signer": self.manifest.signer,
            "signed_gate_plugin_signature_sha256": self.manifest.signature_sha256,
            "signed_gate_plugin_sandbox_mode": self.manifest.sandbox_mode,
            "signed_gate_plugin_rule_count": len(self.rules),
            "signed_gate_plugin_rule_ids": [rule.rule_id for rule in self.rules],
        }


@dataclass(slots=True, frozen=True)
class SignedIngressPluginLifecycleTransition:
    action: str
    previous_plugin_ref: str
    new_plugin_ref: str


def list_signed_ingress_plugins() -> tuple[str, ...]:
    return tuple(sorted(_SIGNED_INGRESS_PLUGIN_REGISTRY.keys()))


def resolve_optional_signed_ingress_plugin(
    plugin_ref: Any,
    *,
    core_major_version: int = 1,
) -> SignedIngressPlugin | None:
    normalized_ref = str(plugin_ref or "").strip()
    if not normalized_ref:
        return None
    return resolve_signed_ingress_plugin(normalized_ref, core_major_version=core_major_version)


def resolve_signed_ingress_plugin(
    plugin_ref: str,
    *,
    core_major_version: int = 1,
) -> SignedIngressPlugin:
    normalized_ref = str(plugin_ref).strip()
    if not normalized_ref:
        raise ValueError("INGRESS_SIGNED_PLUGIN_REF_INVALID: signed_gate_plugin_ref cannot be empty.")
    plugin = _SIGNED_INGRESS_PLUGIN_REGISTRY.get(normalized_ref)
    if plugin is None:
        allowed = ", ".join(list_signed_ingress_plugins()) or "<none>"
        raise ValueError(
            "INGRESS_SIGNED_PLUGIN_UNKNOWN: "
            f"unknown signed_gate_plugin_ref '{normalized_ref}'. Allowed refs: [{allowed}]."
        )
    _validate_plugin_compatibility(plugin, core_major_version=core_major_version)
    _validate_plugin_signer(plugin)
    _validate_plugin_sandbox_policy(plugin)
    _validate_plugin_signature(plugin)
    return plugin


def classify_signed_plugin_lifecycle_transition(
    *,
    previous_plugin_ref: str,
    new_plugin_ref: str,
    active_run_count: int = 0,
) -> SignedIngressPluginLifecycleTransition:
    previous_ref = str(previous_plugin_ref).strip()
    new_ref = str(new_plugin_ref).strip()
    if previous_ref == new_ref:
        action = "none"
    elif not previous_ref and new_ref:
        action = "load"
    elif previous_ref and not new_ref:
        action = "unload"
    else:
        action = "reload"
    if action in {"unload", "reload"} and int(active_run_count) > 0:
        raise ValueError(
            "INGRESS_SIGNED_PLUGIN_LIFECYCLE_BLOCKED_ACTIVE_RUNS: "
            "cannot unload or reload signed ingress plugin while active runs exist."
        )
    return SignedIngressPluginLifecycleTransition(
        action=action,
        previous_plugin_ref=previous_ref,
        new_plugin_ref=new_ref,
    )


def _validate_plugin_compatibility(plugin: SignedIngressPlugin, *, core_major_version: int) -> None:
    if int(plugin.manifest.compatible_core_major) == int(core_major_version):
        return
    raise ValueError(
        "INGRESS_SIGNED_PLUGIN_INCOMPATIBLE_CORE: "
        f"plugin '{plugin.manifest.plugin_ref}' requires core major "
        f"{plugin.manifest.compatible_core_major}, expected {core_major_version}."
    )


def _validate_plugin_signer(plugin: SignedIngressPlugin) -> None:
    signer = str(plugin.manifest.signer).strip()
    if signer in _TRUSTED_SIGNERS:
        return
    raise ValueError(
        "INGRESS_SIGNED_PLUGIN_SIGNER_UNTRUSTED: "
        f"plugin signer '{signer}' is not trusted."
    )


def _validate_plugin_sandbox_policy(plugin: SignedIngressPlugin) -> None:
    sandbox_mode = str(plugin.manifest.sandbox_mode).strip().lower()
    if sandbox_mode == _SANDBOX_MODE_DECLARATIVE_ONLY:
        return
    raise ValueError(
        "INGRESS_SIGNED_PLUGIN_SANDBOX_POLICY_INVALID: "
        f"plugin '{plugin.manifest.plugin_ref}' uses unsupported sandbox_mode '{sandbox_mode}'."
    )


def _validate_plugin_signature(plugin: SignedIngressPlugin) -> None:
    expected_signature = _signature_digest(_signature_payload(plugin))
    if expected_signature == str(plugin.manifest.signature_sha256).strip().lower():
        return
    raise ValueError(
        "INGRESS_SIGNED_PLUGIN_SIGNATURE_INVALID: "
        f"signature check failed for plugin '{plugin.manifest.plugin_ref}'."
    )


def _signature_payload(plugin: SignedIngressPlugin) -> dict[str, Any]:
    return {
        "plugin_ref": plugin.manifest.plugin_ref,
        "version": plugin.manifest.version,
        "compatible_core_major": int(plugin.manifest.compatible_core_major),
        "signer": plugin.manifest.signer,
        "sandbox_mode": plugin.manifest.sandbox_mode,
        "rules": [rule.to_payload() for rule in plugin.rules],
    }


def _signature_digest(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _build_signed_plugin(
    *,
    plugin_ref: str,
    version: str,
    compatible_core_major: int,
    signer: str,
    rules: tuple[SignedIngressPluginRule, ...],
    sandbox_mode: str = _SANDBOX_MODE_DECLARATIVE_ONLY,
) -> SignedIngressPlugin:
    manifest = SignedIngressPluginManifest(
        plugin_ref=plugin_ref,
        version=version,
        compatible_core_major=compatible_core_major,
        signer=signer,
        signature_sha256="",
        sandbox_mode=sandbox_mode,
    )
    unsigned = SignedIngressPlugin(manifest=manifest, rules=rules)
    signature = _signature_digest(_signature_payload(unsigned))
    return SignedIngressPlugin(manifest=replace(manifest, signature_sha256=signature), rules=rules)


_SIGNED_INGRESS_PLUGINS: tuple[SignedIngressPlugin, ...] = (
    _build_signed_plugin(
        plugin_ref="plugin://trusted/signed-v1",
        version="1.0.0",
        compatible_core_major=1,
        signer="exo-security",
        rules=(
            SignedIngressPluginRule(
                rule_id="signed-deny-credential-exfil",
                action="deny",
                match_type="contains_any",
                patterns=("private key", "seed phrase", "api key"),
                reason_code="INGRESS_SIGNED_PLUGIN_DENY_CREDENTIAL_EXFIL",
                message="Signed ingress plugin denied potential credential exfiltration pattern.",
            ),
            SignedIngressPluginRule(
                rule_id="signed-escalate-system-bypass",
                action="escalate",
                match_type="regex_any",
                patterns=(r"(?:disable|bypass)\s+(?:all\s+)?(?:security|safety)\s+(?:controls|checks)",),
                reason_code="INGRESS_SIGNED_PLUGIN_ESCALATE_BYPASS_PATTERN",
                message="Signed ingress plugin escalated potential security-control bypass request.",
            ),
        ),
    ),
    _build_signed_plugin(
        plugin_ref="plugin://trusted/signed-v2",
        version="1.1.0",
        compatible_core_major=1,
        signer="exo-security",
        rules=(
            SignedIngressPluginRule(
                rule_id="signed-v2-deny-secret-export",
                action="deny",
                match_type="contains_any",
                patterns=("export secrets", "dump credentials", "reveal private key"),
                reason_code="INGRESS_SIGNED_PLUGIN_DENY_SECRET_EXPORT",
                message="Signed ingress plugin denied explicit secret export intent.",
            ),
            SignedIngressPluginRule(
                rule_id="signed-v2-escalate-data-exfil",
                action="escalate",
                match_type="regex_any",
                patterns=(r"(?:exfiltrate|extract)\s+(?:customer|tenant|internal)\s+data",),
                reason_code="INGRESS_SIGNED_PLUGIN_ESCALATE_DATA_EXFIL",
                message="Signed ingress plugin escalated potential data exfiltration intent.",
            ),
        ),
    ),
)

_SIGNED_INGRESS_PLUGIN_REGISTRY: dict[str, SignedIngressPlugin] = {
    plugin.manifest.plugin_ref: plugin for plugin in _SIGNED_INGRESS_PLUGINS
}

