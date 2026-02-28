"""
File: evidence_bundle.py
Path: src/compliance/evidence_bundle.py
Role: Build structured release evidence bundles for governance workflows.
Used By:
 - scripts/release/verify_gates.py
 - tests/integration/test_evidence_bundle_generation.py
Depends On:
 - src/audit/trail.py
Notes:
 - Bundle remains JSON-like for easy storage/export.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.audit.trail import AuditChainRecord, verify_chain


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

