"""
File: audit_schemas.py
Path: src/api/schemas/audit_schemas.py
Role: Pydantic schemas for tenant audit query and report endpoints.
Used By:
 - src/api/routers/audit.py
Depends On:
 - pydantic
Notes:
 - Endpoints expose tenant-scoped audit records only.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AuditEventResponse(BaseModel):
    event_id: str
    correlation_id: str
    tenant_id: str
    event_type: str
    payload: dict = Field(default_factory=dict)


class AuditEventListResponse(BaseModel):
    tenant_id: str
    correlation_id: str = ""
    total: int
    events: list[AuditEventResponse] = Field(default_factory=list)


class AuditReportResponse(BaseModel):
    tenant_id: str
    total_events: int
    by_event_type: dict[str, int] = Field(default_factory=dict)


class AuditCleanupRequest(BaseModel):
    max_records: int = Field(default=0, ge=0, description="Retention cap for tenant audit records (0 = use system default)")


class AuditCleanupResponse(BaseModel):
    tenant_id: str
    pruned_records: int
    retained_cap: int


class AuditExportBundleResponse(BaseModel):
    tenant_id: str
    record_count: int
    chain_valid: bool
    last_record_hash: str = ""
    exported_at_utc: str = ""
    signature_version: str = "v1"
    signature: str = ""
    event_type_counts: dict[str, int] = Field(default_factory=dict)
    records: list[AuditEventResponse] = Field(default_factory=list)


class AuditExportFileRequest(BaseModel):
    limit: int = Field(default=500, ge=1, le=5000)
    filename_prefix: str = Field(default="audit_bundle", min_length=1, max_length=64)


class AuditExportFileResponse(BaseModel):
    tenant_id: str
    file_path: str
    record_count: int
    signature_version: str = "v1"
    signature: str
    chain_valid: bool
    last_record_hash: str = ""


class AuditVerifyRequest(BaseModel):
    file_path: str = ""
    bundle: dict = Field(default_factory=dict)


class AuditVerifyResponse(BaseModel):
    tenant_id: str
    signature_version: str = ""
    verified_with_version: str = ""
    signature_valid: bool
    chain_valid: bool
    verified: bool
    reason: str = ""
