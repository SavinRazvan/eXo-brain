"""
File: test_evidence_bundle_generation.py
Path: tests/modules/audit/test_evidence_bundle_generation.py
Role: Integration test for compliance evidence bundle generation.
Used By:
 - pytest
Depends On:
 - src/compliance/evidence_bundle.py
 - src/audit/trail.py
Notes:
 - Verifies evidence includes gate payloads and audit chain validity.
"""

from src.audit.trail import chain_record
from src.compliance.evidence_bundle import build_evidence_bundle


def test_build_evidence_bundle_reports_audit_integrity() -> None:
    first = chain_record({"event": "one"}, previous_hash="")
    second = chain_record({"event": "two"}, previous_hash=first.record_hash)
    bundle = build_evidence_bundle(
        release_id="rel_1",
        gate_results={"tests": "pass"},
        audit_records=[first, second],
        metadata={"commit": "abc"},
    )
    assert bundle.release_id == "rel_1"
    assert bundle.gate_results["tests"] == "pass"
    assert bundle.audit_chain_valid is True

