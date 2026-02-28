"""
File: test_audit_chain_integrity.py
Path: tests/modules/audit/test_audit_chain_integrity.py
Role: Security tests for tamper-evident audit chain verification.
Used By:
 - pytest
Depends On:
 - src/audit/trail.py
Notes:
 - Detects payload tampering in chained audit records.
"""

from src.audit.trail import chain_record, verify_chain


def test_audit_chain_detects_tampering() -> None:
    first = chain_record({"event": "a"}, previous_hash="")
    second = chain_record({"event": "b"}, previous_hash=first.record_hash)
    assert verify_chain([first, second]) is True
    second.payload["event"] = "mutated"
    assert verify_chain([first, second]) is False

