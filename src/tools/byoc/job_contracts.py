"""
File: job_contracts.py
Path: src/tools/byoc/job_contracts.py
Role: Typed BYOC pull-worker job/result envelopes for deterministic tool runtime handoff.
Used By:
 - src/tools/byoc/connector_runtime.py
 - src/api/routers/runtime_control.py
Depends On:
 - dataclasses
 - typing
Notes:
 - Envelopes are intentionally provider-neutral and tenant-scoped.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class ByocResultStatus:
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"



@dataclass(slots=True)
class ByocToolJobEnvelope:
    job_id: str
    tenant_id: str
    run_id: str
    call_id: str
    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    timeout_ms: int = 30000
    correlation_id: str = ""
    idempotency_key: str = ""
    lease_token: str = ""
    lease_expires_at_epoch: int = 0
    claim_attempt: int = 0
    tool_version: str = ""
    package_ref: str = ""
    entry_file: str = ""
    entrypoint: str = ""
    artifact_bundle_hash_sha256: str = ""
    artifact_bundle_signature_hmac_sha256: str = ""
    artifact_signature_version: str = ""


@dataclass(slots=True)
class ByocToolResultEnvelope:
    job_id: str
    tenant_id: str
    run_id: str
    call_id: str
    tool_name: str
    status: str = ByocResultStatus.SUCCESS
    output: dict[str, Any] = field(default_factory=dict)
    error_code: str = ""
    error_message: str = ""
    retryable: bool = False
    idempotency_key: str = ""
    lease_token: str = ""
    tool_version: str = ""
    artifact_bundle_hash_sha256: str = ""
    artifact_bundle_signature_hmac_sha256: str = ""
    artifact_signature_version: str = ""

