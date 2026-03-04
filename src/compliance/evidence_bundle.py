"""
File: evidence_bundle.py
Path: src/compliance/evidence_bundle.py
Role: Build structured release evidence bundles for governance workflows.
Used By:
 - scripts/release/verify_gates.py
 - tests/modules/audit/test_evidence_bundle_generation.py
Depends On:
 - src/audit/trail.py
Notes:
 - Bundle remains JSON-like for easy storage/export.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from typing import Any

from src.audit.trail import AuditChainRecord, chain_record, verify_chain


@dataclass(slots=True)
class EvidenceBundle:
    release_id: str
    gate_results: dict[str, Any] = field(default_factory=dict)
    audit_chain_valid: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


def build_evidence_bundle(
    release_id: str,
    gate_results: dict[str, Any],
    audit_records: list[AuditChainRecord],
    metadata: dict[str, Any] | None = None,
) -> EvidenceBundle:
    return EvidenceBundle(
        release_id=release_id,
        gate_results=dict(gate_results),
        audit_chain_valid=verify_chain(audit_records),
        metadata=dict(metadata or {}),
    )


def sign_bundle_payload(payload: dict[str, Any], secret: str) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hmac.new(
        str(secret).encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_signed_bundle_payload(payload: dict[str, Any], signature: str, secret: str) -> bool:
    expected = sign_bundle_payload(payload, secret)
    return hmac.compare_digest(expected, str(signature))


def build_signing_keyring(
    *,
    legacy_secret: str,
    versioned_secrets: dict[str, str] | None = None,
) -> dict[str, str]:
    keyring: dict[str, str] = {}
    for version, secret in dict(versioned_secrets or {}).items():
        ver = str(version).strip()
        sec = str(secret).strip()
        if ver and sec:
            keyring[ver] = sec
    legacy = str(legacy_secret).strip()
    if legacy and "v1" not in keyring:
        keyring["v1"] = legacy
    return keyring


def resolve_signing_secret(
    *,
    active_version: str,
    keyring: dict[str, str],
) -> tuple[str, str]:
    target = str(active_version).strip() or "v1"
    if target in keyring and str(keyring[target]).strip():
        return target, str(keyring[target]).strip()
    if "v1" in keyring and str(keyring["v1"]).strip():
        return "v1", str(keyring["v1"]).strip()
    for version in sorted(keyring.keys()):
        secret = str(keyring[version]).strip()
        if secret:
            return version, secret
    return target, ""


def verify_signed_bundle_with_keyring(
    *,
    payload: dict[str, Any],
    signature: str,
    declared_version: str,
    keyring: dict[str, str],
) -> tuple[bool, str]:
    declared = str(declared_version).strip()
    if declared and declared in keyring:
        return verify_signed_bundle_payload(payload, signature, keyring[declared]), declared

    if not declared and "v1" in keyring:
        if verify_signed_bundle_payload(payload, signature, keyring["v1"]):
            return True, "v1"

    for version in sorted(keyring.keys()):
        if verify_signed_bundle_payload(payload, signature, keyring[version]):
            return True, version
    return False, ""


def compute_audit_chain_fingerprint(records: list[dict[str, Any]]) -> tuple[bool, str]:
    chain_records: list[AuditChainRecord] = []
    previous_hash = ""
    for record in records:
        chained = chain_record(payload=dict(record), previous_hash=previous_hash)
        chain_records.append(chained)
        previous_hash = chained.record_hash
    return verify_chain(chain_records), (chain_records[-1].record_hash if chain_records else "")

