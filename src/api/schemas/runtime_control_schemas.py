"""
File: runtime_control_schemas.py
Path: src/api/schemas/runtime_control_schemas.py
Role: Pydantic schemas for internal hosted runtime control endpoints.
Used By:
 - src/api/routers/runtime_control.py
Depends On:
 - pydantic
Notes:
 - These endpoints are internal/admin oriented and require valid identity.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RuntimeControlStatsResponse(BaseModel):
    tenant_id: str
    backend_id: str
    control_stats: dict[str, int] = Field(default_factory=dict)
    pool_stats: dict[str, int] = Field(default_factory=dict)


class RuntimeCleanupEventsResponse(BaseModel):
    tenant_id: str
    backend_id: str
    events: list[dict[str, str]] = Field(default_factory=list)


class RuntimeCancellationRequest(BaseModel):
    call_id: str = Field(..., min_length=1, description="Call id to mark for pre-dispatch cancellation.")


class RuntimeCancellationResponse(BaseModel):
    tenant_id: str
    backend_id: str
    call_id: str
    accepted: bool
    pending_cancellations: int


class RuntimeRunRecord(BaseModel):
    tenant_id: str
    session_id: str
    run_id: str
    correlation_id: str
    transport: str
    status: str
    call_ids: list[str] = Field(default_factory=list)
    cancel_requested: bool = False
    cancel_reason: str = ""
    started_at_utc: str = ""
    updated_at_utc: str = ""
    finished_at_utc: str = ""
    terminal_event: str = ""
    terminal_message: str = ""


class RuntimeRunListResponse(BaseModel):
    tenant_id: str
    total: int
    runs: list[RuntimeRunRecord] = Field(default_factory=list)


class RuntimeRunCancelResponse(BaseModel):
    tenant_id: str
    backend_id: str
    run_id: str
    accepted: bool
    forwarded_call_cancellations: int


class ByocWorkerTokenRequest(BaseModel):
    worker_id: str = Field(..., min_length=1)
    ttl_seconds: int | None = Field(default=None, ge=1, le=3600)


class ByocWorkerTokenResponse(BaseModel):
    tenant_id: str
    backend_id: str
    worker_id: str
    token: str


class ByocClaimJobRequest(BaseModel):
    worker_token: str = Field(..., min_length=1)
    request_nonce: str = Field(..., min_length=8)


class ByocClaimJobResponse(BaseModel):
    tenant_id: str
    backend_id: str
    job: dict | None = None


class ByocSubmitResultRequest(BaseModel):
    worker_token: str = Field(..., min_length=1)
    request_nonce: str = Field(..., min_length=8)
    result: dict


class ByocWebhookSubmitResultRequest(BaseModel):
    webhook_secret: str = Field(..., min_length=1)
    webhook_request_id: str = Field(..., min_length=8)
    result: dict


class ByocSubmitResultResponse(BaseModel):
    tenant_id: str
    backend_id: str
    accepted: bool
    duplicate: bool
    reason_code: str


class ByocCleanupRequest(BaseModel):
    force: bool = Field(default=False, description="Run cleanup immediately even if periodic interval has not elapsed.")


class ByocCleanupResponse(BaseModel):
    tenant_id: str
    backend_id: str
    cleanup_stats: dict[str, int] = Field(default_factory=dict)


class ByocDlqRecord(BaseModel):
    job_id: str
    call_id: str
    tool_name: str
    idempotency_key: str
    claim_attempt: str
    dead_letter_reason_code: str
    dead_lettered_at_epoch: str
    replay_count: str


class ByocDlqListResponse(BaseModel):
    tenant_id: str
    backend_id: str
    total: int
    records: list[ByocDlqRecord] = Field(default_factory=list)


class ByocDlqReplayResponse(BaseModel):
    tenant_id: str
    backend_id: str
    job_id: str
    replayed: bool


class ByocGovernanceReasonCount(BaseModel):
    reason_code: str
    count: int


class ByocGovernanceCostMetrics(BaseModel):
    window: str = "lifetime"
    cost_microunits_total: int = 0
    cost_limit_microunits: int = 0
    cost_remaining_microunits: int = 0
    utilization_ratio: float = 0.0


class ByocGovernanceSubmissionMetrics(BaseModel):
    window: str = "lifetime"
    submit_attempts_total: int = 0
    rejected_results_total: int = 0
    rejection_rate: float = 0.0


class ByocGovernanceMetricsResponse(BaseModel):
    tenant_id: str
    backend_id: str
    generated_at_utc: str
    cost: ByocGovernanceCostMetrics
    submissions: ByocGovernanceSubmissionMetrics
    rejection_reasons: list[ByocGovernanceReasonCount] = Field(default_factory=list)
