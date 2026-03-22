"""
File: test_integrity_verifier.py
Path: tests/modules/tools/test_integrity_verifier.py
Role: Unit tests for BYOC result vs job artifact metadata parity checks.
Used By:
 - pytest
Depends On:
 - src/tools/byoc/integrity_verifier.py
 - src/tools/byoc/job_contracts.py
Notes:
 - Exercises mismatch and missing-metadata reason codes deterministically.
"""

from __future__ import annotations

from dataclasses import replace

from src.tools.byoc.integrity_verifier import verify_result_artifact_metadata
from src.tools.byoc.job_contracts import ByocToolJobEnvelope, ByocToolResultEnvelope


def _base_job() -> ByocToolJobEnvelope:
    return ByocToolJobEnvelope(
        job_id="j1",
        tenant_id="t1",
        run_id="r1",
        call_id="c1",
        tool_name="echo",
    )


def _base_result() -> ByocToolResultEnvelope:
    return ByocToolResultEnvelope(
        job_id="j1",
        tenant_id="t1",
        run_id="r1",
        call_id="c1",
        tool_name="echo",
        idempotency_key="k1",
        lease_token="l1",
    )


def test_version_mismatch_returns_reason() -> None:
    reason = verify_result_artifact_metadata(
        expected_job=replace(_base_job(), artifact_signature_version="v1"),
        submitted_result=replace(_base_result(), artifact_signature_version="v2"),
    )
    assert reason == "BYOC_ARTIFACT_SIGNATURE_VERSION_MISMATCH"


def test_hash_mismatch_returns_reason() -> None:
    reason = verify_result_artifact_metadata(
        expected_job=replace(_base_job(), artifact_bundle_hash_sha256="aa"),
        submitted_result=replace(_base_result(), artifact_bundle_hash_sha256="bb"),
    )
    assert reason == "BYOC_ARTIFACT_INTEGRITY_MISMATCH"


def test_signature_mismatch_returns_reason() -> None:
    reason = verify_result_artifact_metadata(
        expected_job=replace(
            _base_job(),
            artifact_bundle_hash_sha256="",
            artifact_bundle_signature_hmac_sha256="sig1",
        ),
        submitted_result=replace(
            _base_result(),
            artifact_bundle_hash_sha256="",
            artifact_bundle_signature_hmac_sha256="sig2",
        ),
    )
    assert reason == "BYOC_ARTIFACT_INTEGRITY_MISMATCH"


def test_expected_hash_without_submitted_returns_missing() -> None:
    reason = verify_result_artifact_metadata(
        expected_job=replace(_base_job(), artifact_bundle_hash_sha256="aa"),
        submitted_result=replace(_base_result(), artifact_bundle_hash_sha256=""),
    )
    assert reason == "BYOC_ARTIFACT_INTEGRITY_MISSING"


def test_expected_signature_without_submitted_returns_missing() -> None:
    reason = verify_result_artifact_metadata(
        expected_job=replace(
            _base_job(),
            artifact_bundle_hash_sha256="",
            artifact_bundle_signature_hmac_sha256="aa",
        ),
        submitted_result=replace(
            _base_result(),
            artifact_bundle_hash_sha256="",
            artifact_bundle_signature_hmac_sha256="",
        ),
    )
    assert reason == "BYOC_ARTIFACT_INTEGRITY_MISSING"
