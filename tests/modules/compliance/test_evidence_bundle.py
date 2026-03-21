"""
File: test_evidence_bundle.py
Path: tests/modules/compliance/test_evidence_bundle.py
Role: Unit tests for evidence bundle signing, keyring resolution, and audit fingerprints.
Used By:
 - pytest
Depends On:
 - src/compliance/evidence_bundle.py
Notes:
 - Complements audit integration tests; targets branch-complete coverage for compliance helpers.
"""

from src.audit.trail import chain_record
from src.compliance.evidence_bundle import (
    build_evidence_bundle,
    build_signing_keyring,
    compute_audit_chain_fingerprint,
    resolve_signing_secret,
    sign_bundle_payload,
    verify_signed_bundle_payload,
    verify_signed_bundle_with_keyring,
)


def test_sign_and_verify_round_trip() -> None:
    payload = {"release_id": "r1", "ok": True}
    secret = "hunter2"
    sig = sign_bundle_payload(payload, secret)
    assert verify_signed_bundle_payload(payload, sig, secret) is True
    assert verify_signed_bundle_payload(payload, sig + "x", secret) is False


def test_build_signing_keyring_prefers_explicit_v1_and_skips_blanks() -> None:
    ring = build_signing_keyring(
        legacy_secret="  legacy  ",
        versioned_secrets={"v2": " two ", "": "skip", "x": "   "},
    )
    assert ring["v1"] == "legacy"
    assert ring["v2"] == "two"
    assert "x" not in ring


def test_build_signing_keyring_legacy_only_when_v1_present() -> None:
    ring = build_signing_keyring(legacy_secret="L", versioned_secrets={"v1": "explicit"})
    assert ring["v1"] == "explicit"


def test_resolve_signing_secret_active_hits_then_v1_then_sorted() -> None:
    keyring = {"v3": "c", "v1": "a", "v2": "b"}
    ver, sec = resolve_signing_secret(active_version="v2", keyring=keyring)
    assert ver == "v2" and sec == "b"

    ver, sec = resolve_signing_secret(active_version="missing", keyring=keyring)
    assert ver == "v1" and sec == "a"

    ver, sec = resolve_signing_secret(active_version="", keyring={"v9": "z", "v8": "y"})
    assert ver == "v8" and sec == "y"

    ver, sec = resolve_signing_secret(active_version="v0", keyring={})
    assert ver == "v0" and sec == ""


def test_verify_signed_bundle_with_keyring_declared_and_fallbacks() -> None:
    payload = {"a": 1}
    secret_v1 = "s1"
    secret_v2 = "s2"
    sig_v2 = sign_bundle_payload(payload, secret_v2)
    keyring = build_signing_keyring(legacy_secret=secret_v1, versioned_secrets={"v2": secret_v2})

    ok, ver = verify_signed_bundle_with_keyring(
        payload=payload, signature=sig_v2, declared_version="v2", keyring=keyring
    )
    assert ok and ver == "v2"

    sig_v1 = sign_bundle_payload(payload, secret_v1)
    ok, ver = verify_signed_bundle_with_keyring(
        payload=payload, signature=sig_v1, declared_version="", keyring=keyring
    )
    assert ok and ver == "v1"

    ok, ver = verify_signed_bundle_with_keyring(
        payload=payload, signature=sig_v2, declared_version="nope", keyring=keyring
    )
    assert ok and ver == "v2"

    ok, ver = verify_signed_bundle_with_keyring(
        payload=payload, signature="deadbeef", declared_version="v2", keyring=keyring
    )
    assert ok is False and ver == "v2"

    ok, ver = verify_signed_bundle_with_keyring(
        payload=payload, signature="deadbeef", declared_version="ghost", keyring=keyring
    )
    assert ok is False and ver == ""


def test_build_evidence_bundle_copies_inputs() -> None:
    rec = chain_record({"e": 1}, previous_hash="")
    bundle = build_evidence_bundle(
        release_id="r9",
        gate_results={"g": 1},
        audit_records=[rec],
        metadata=None,
    )
    assert bundle.release_id == "r9"
    assert bundle.metadata == {}
    assert bundle.audit_chain_valid is True


def test_compute_audit_chain_fingerprint_empty_and_valid() -> None:
    ok, fp = compute_audit_chain_fingerprint([])
    assert ok is True
    assert fp == ""

    ok, fp = compute_audit_chain_fingerprint([{"e": 1}, {"e": 2}])
    assert ok is True
    assert len(fp) == 64
