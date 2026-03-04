"""
File: integrity_verifier.py
Path: src/tools/byoc/integrity_verifier.py
Role: Deterministic verifier for BYOC artifact integrity metadata parity between claimed jobs and submitted results.
Used By:
 - src/tools/byoc/connector_runtime.py
Depends On:
 - src/tools/byoc/job_contracts.py
Notes:
 - This verifier compares metadata identity only (hash/signature/version), not cryptographic proof validation.
 - Worker-side cryptographic verification can layer on top of this deterministic parity guard.
"""

from __future__ import annotations

from src.tools.byoc.job_contracts import ByocToolJobEnvelope, ByocToolResultEnvelope


def verify_result_artifact_metadata(
    *,
    expected_job: ByocToolJobEnvelope,
    submitted_result: ByocToolResultEnvelope,
) -> str:
    """Return deterministic reason code when result metadata mismatches claimed job.

    Returns empty string when metadata is consistent.
    """
    expected_version = str(expected_job.artifact_signature_version or "").strip()
    submitted_version = str(submitted_result.artifact_signature_version or "").strip()
    if expected_version and submitted_version and expected_version != submitted_version:
        return "BYOC_ARTIFACT_SIGNATURE_VERSION_MISMATCH"

    expected_hash = str(expected_job.artifact_bundle_hash_sha256 or "").strip()
    submitted_hash = str(submitted_result.artifact_bundle_hash_sha256 or "").strip()
    expected_sig = str(expected_job.artifact_bundle_signature_hmac_sha256 or "").strip()
    submitted_sig = str(submitted_result.artifact_bundle_signature_hmac_sha256 or "").strip()

    if expected_hash and submitted_hash and expected_hash != submitted_hash:
        return "BYOC_ARTIFACT_INTEGRITY_MISMATCH"
    if expected_sig and submitted_sig and expected_sig != submitted_sig:
        return "BYOC_ARTIFACT_INTEGRITY_MISMATCH"

    if expected_hash and not submitted_hash:
        return "BYOC_ARTIFACT_INTEGRITY_MISSING"
    if expected_sig and not submitted_sig:
        return "BYOC_ARTIFACT_INTEGRITY_MISSING"
    return ""
