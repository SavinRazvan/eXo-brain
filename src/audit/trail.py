"""
File: trail.py
Path: src/audit/trail.py
Role: Tamper-evident audit trail helpers for decision lineage reconstruction.
Used By:
 - src/compliance/evidence_bundle.py
Depends On:
 - hashlib
Notes:
 - Hash chaining provides lightweight tamper evidence for local baseline.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class AuditChainRecord:
    payload: dict[str, Any]
    previous_hash: str
    record_hash: str


def chain_record(payload: dict[str, Any], previous_hash: str) -> AuditChainRecord:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(f"{previous_hash}:{serialized}".encode("utf-8")).hexdigest()
    return AuditChainRecord(payload=dict(payload), previous_hash=previous_hash, record_hash=digest)


def verify_chain(records: list[AuditChainRecord]) -> bool:
    previous = ""
    for record in records:
        expected = chain_record(record.payload, previous)
        if expected.record_hash != record.record_hash or record.previous_hash != previous:
            return False
        previous = record.record_hash
    return True

