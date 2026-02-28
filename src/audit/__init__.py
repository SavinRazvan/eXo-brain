"""
File: __init__.py
Path: src/audit/__init__.py
Role: Public exports for audit trail helpers.
Used By:
 - src/compliance/evidence_bundle.py
 - tests/security/test_audit_chain_integrity.py
Depends On:
 - src/audit/trail.py
Notes:
 - Keep audit primitives simple and verifiable.
"""

from src.audit.trail import AuditChainRecord, chain_record, verify_chain

__all__ = ["AuditChainRecord", "chain_record", "verify_chain"]

