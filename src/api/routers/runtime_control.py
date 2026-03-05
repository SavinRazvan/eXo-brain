"""
File: runtime_control.py
Path: src/api/routers/runtime_control.py
Role: Internal/admin APIs for hosted runtime controls and lifecycle observability.
Used By:
 - src/api/app.py
Depends On:
 - fastapi
 - src/api/dependencies.py
 - src/api/schemas/runtime_control_schemas.py
Notes:
 - Endpoints are tenant-scoped and require authenticated identity.
 - Controls are best-effort and intentionally additive for operations visibility.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from src.api.dependencies import get_tenant_context, require_valid_identity
from src.api.schemas.runtime_control_schemas import (
    ByocCleanupRequest,
    ByocCleanupResponse,
    ByocClaimJobRequest,
    ByocClaimJobResponse,
    ByocSubmitResultRequest,
    ByocSubmitResultResponse,
    ByocWebhookSubmitResultRequest,
    ByocWorkerTokenRequest,
    ByocWorkerTokenResponse,
    RuntimeCancellationRequest,
    RuntimeCancellationResponse,
    RuntimeCleanupEventsResponse,
    RuntimeControlStatsResponse,
    RuntimeRunCancelResponse,
    RuntimeRunListResponse,
    RuntimeRunRecord,
)
from src.core.run_control_registry import RunControlRegistry
from src.identity.contracts import IdentityContext
from src.runtime.tenant_runtime import TenantRuntimeContext
from src.tools.byoc.job_contracts import ByocToolResultEnvelope

router = APIRouter(tags=["runtime-control"])


def _resolve_runtime_adapter(ctx: TenantRuntimeContext):
    adapter = ctx.tool_executor.execution_adapter()
    if adapter is None:
        raise HTTPException(
            status_code=409,
            detail="Hosted runtime adapter is not enabled for this tenant.",
        )
    return adapter


def _resolve_run_registry(request: Request) -> RunControlRegistry:
    registry = getattr(request.app.state, "run_control_registry", None)
    if registry is None:
        raise HTTPException(status_code=503, detail="Run control registry is not configured on this server.")
    return registry


def _resolve_byoc_adapter(ctx: TenantRuntimeContext):
    adapter = _resolve_runtime_adapter(ctx)
    if adapter.backend_id != "byoc_pull_worker_runtime":
        raise HTTPException(
            status_code=409,
            detail="BYOC runtime adapter is not enabled for this tenant.",
        )
    return adapter


def _to_byoc_result_envelope(payload: dict, tenant_id: str) -> ByocToolResultEnvelope:
    return ByocToolResultEnvelope(
        job_id=str(payload.get("job_id", "")),
        tenant_id=str(payload.get("tenant_id", tenant_id)),
        run_id=str(payload.get("run_id", "")),
        call_id=str(payload.get("call_id", "")),
        tool_name=str(payload.get("tool_name", "")),
        status=str(payload.get("status", "success")),
        output=dict(payload.get("output", {}) or {}),
        error_code=str(payload.get("error_code", "")),
        error_message=str(payload.get("error_message", "")),
        retryable=bool(payload.get("retryable", False)),
        idempotency_key=str(payload.get("idempotency_key", "")),
        lease_token=str(payload.get("lease_token", "")),
        tool_version=str(payload.get("tool_version", "")),
        artifact_bundle_hash_sha256=str(payload.get("artifact_bundle_hash_sha256", "")),
        artifact_bundle_signature_hmac_sha256=str(payload.get("artifact_bundle_signature_hmac_sha256", "")),
        artifact_signature_version=str(payload.get("artifact_signature_version", "")),
    )


@router.get(
    "/{tenant_id}/admin/runtime/control-stats",
    response_model=RuntimeControlStatsResponse,
)
async def get_runtime_control_stats(
    tenant_id: str,
    ctx: TenantRuntimeContext = Depends(get_tenant_context),
    _identity: IdentityContext = Depends(require_valid_identity),
) -> RuntimeControlStatsResponse:
    adapter = _resolve_runtime_adapter(ctx)
    pool_stats = getattr(adapter, "pool_stats", lambda: {})()
    stats_method = getattr(adapter, "control_stats_for_tenant", None)
    control_stats = adapter.control_stats()
    if callable(stats_method):
        control_stats = stats_method(tenant_id=tenant_id)
    return RuntimeControlStatsResponse(
        tenant_id=tenant_id,
        backend_id=adapter.backend_id,
        control_stats=control_stats,
        pool_stats=pool_stats,
    )


@router.get(
    "/{tenant_id}/admin/runtime/cleanup-events",
    response_model=RuntimeCleanupEventsResponse,
)
async def get_runtime_cleanup_events(
    tenant_id: str,
    limit: int = Query(default=20, ge=1, le=200),
    ctx: TenantRuntimeContext = Depends(get_tenant_context),
    _identity: IdentityContext = Depends(require_valid_identity),
) -> RuntimeCleanupEventsResponse:
    adapter = _resolve_runtime_adapter(ctx)
    return RuntimeCleanupEventsResponse(
        tenant_id=tenant_id,
        backend_id=adapter.backend_id,
        events=adapter.cleanup_events(limit=limit),
    )


@router.post(
    "/{tenant_id}/admin/runtime/cancellations",
    response_model=RuntimeCancellationResponse,
)
async def request_runtime_cancellation(
    tenant_id: str,
    body: RuntimeCancellationRequest,
    ctx: TenantRuntimeContext = Depends(get_tenant_context),
    _identity: IdentityContext = Depends(require_valid_identity),
) -> RuntimeCancellationResponse:
    adapter = _resolve_runtime_adapter(ctx)
    accepted = adapter.request_cancellation(body.call_id)
    stats = adapter.control_stats()
    return RuntimeCancellationResponse(
        tenant_id=tenant_id,
        backend_id=adapter.backend_id,
        call_id=body.call_id,
        accepted=accepted,
        pending_cancellations=int(stats.get("pending_cancellations", 0)),
    )


@router.delete(
    "/{tenant_id}/admin/runtime/cancellations/{call_id}",
    response_model=RuntimeCancellationResponse,
)
async def clear_runtime_cancellation(
    tenant_id: str,
    call_id: str,
    ctx: TenantRuntimeContext = Depends(get_tenant_context),
    _identity: IdentityContext = Depends(require_valid_identity),
) -> RuntimeCancellationResponse:
    adapter = _resolve_runtime_adapter(ctx)
    clear_method = getattr(adapter, "clear_cancellation", None)
    accepted = False
    if callable(clear_method):
        accepted = bool(clear_method(call_id))
    stats = adapter.control_stats()
    return RuntimeCancellationResponse(
        tenant_id=tenant_id,
        backend_id=adapter.backend_id,
        call_id=call_id,
        accepted=accepted,
        pending_cancellations=int(stats.get("pending_cancellations", 0)),
    )


@router.get(
    "/{tenant_id}/admin/runtime/runs",
    response_model=RuntimeRunListResponse,
)
async def list_runtime_runs(
    tenant_id: str,
    request: Request,
    limit: int = Query(default=50, ge=1, le=500),
    _ctx: TenantRuntimeContext = Depends(get_tenant_context),
    _identity: IdentityContext = Depends(require_valid_identity),
) -> RuntimeRunListResponse:
    registry = _resolve_run_registry(request)
    records = registry.list_runs(tenant_id=tenant_id, limit=limit)
    return RuntimeRunListResponse(
        tenant_id=tenant_id,
        total=len(records),
        runs=[RuntimeRunRecord.model_validate(record) for record in records],
    )


@router.get(
    "/{tenant_id}/admin/runtime/runs/{run_id}",
    response_model=RuntimeRunRecord,
)
async def get_runtime_run(
    tenant_id: str,
    run_id: str,
    request: Request,
    _ctx: TenantRuntimeContext = Depends(get_tenant_context),
    _identity: IdentityContext = Depends(require_valid_identity),
) -> RuntimeRunRecord:
    registry = _resolve_run_registry(request)
    record = registry.get_run(tenant_id=tenant_id, run_id=run_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found for tenant '{tenant_id}'.")
    return RuntimeRunRecord.model_validate(record)


@router.post(
    "/{tenant_id}/admin/runtime/runs/{run_id}/cancel",
    response_model=RuntimeRunCancelResponse,
)
async def cancel_runtime_run(
    tenant_id: str,
    run_id: str,
    request: Request,
    ctx: TenantRuntimeContext = Depends(get_tenant_context),
    _identity: IdentityContext = Depends(require_valid_identity),
) -> RuntimeRunCancelResponse:
    adapter = _resolve_runtime_adapter(ctx)
    registry = _resolve_run_registry(request)

    accepted = registry.request_cancel(
        tenant_id=tenant_id,
        run_id=run_id,
        reason="admin_runtime_cancel_endpoint",
    )
    call_ids = registry.call_ids_for_run(tenant_id=tenant_id, run_id=run_id)
    forwarded = 0
    for call_id in call_ids:
        if adapter.request_cancellation(call_id):
            forwarded += 1
    if accepted and forwarded > 0:
        registry.mark_terminal(
            tenant_id=tenant_id,
            run_id=run_id,
            status="cancelled",
            terminal_event="admin_cancel_forwarded",
        )
    return RuntimeRunCancelResponse(
        tenant_id=tenant_id,
        backend_id=adapter.backend_id,
        run_id=run_id,
        accepted=accepted,
        forwarded_call_cancellations=forwarded,
    )


@router.post(
    "/{tenant_id}/admin/byoc/worker-token",
    response_model=ByocWorkerTokenResponse,
)
async def issue_byoc_worker_token(
    tenant_id: str,
    body: ByocWorkerTokenRequest,
    ctx: TenantRuntimeContext = Depends(get_tenant_context),
    _identity: IdentityContext = Depends(require_valid_identity),
) -> ByocWorkerTokenResponse:
    adapter = _resolve_byoc_adapter(ctx)
    token = adapter.issue_worker_token(
        tenant_id=tenant_id,
        worker_id=body.worker_id,
        ttl_seconds=body.ttl_seconds,
    )
    return ByocWorkerTokenResponse(
        tenant_id=tenant_id,
        backend_id=adapter.backend_id,
        worker_id=body.worker_id,
        token=token,
    )


@router.post(
    "/{tenant_id}/admin/byoc/jobs/claim",
    response_model=ByocClaimJobResponse,
)
async def claim_byoc_job(
    tenant_id: str,
    body: ByocClaimJobRequest,
    ctx: TenantRuntimeContext = Depends(get_tenant_context),
    _identity: IdentityContext = Depends(require_valid_identity),
) -> ByocClaimJobResponse:
    adapter = _resolve_byoc_adapter(ctx)
    try:
        job = adapter.claim_next_job(
            tenant_id=tenant_id,
            worker_token=body.worker_token,
            request_nonce=body.request_nonce,
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return ByocClaimJobResponse(
        tenant_id=tenant_id,
        backend_id=adapter.backend_id,
        job=job,
    )


@router.post(
    "/{tenant_id}/admin/byoc/jobs/submit",
    response_model=ByocSubmitResultResponse,
)
async def submit_byoc_job_result(
    tenant_id: str,
    body: ByocSubmitResultRequest,
    ctx: TenantRuntimeContext = Depends(get_tenant_context),
    _identity: IdentityContext = Depends(require_valid_identity),
) -> ByocSubmitResultResponse:
    adapter = _resolve_byoc_adapter(ctx)
    payload = body.result or {}
    try:
        envelope = _to_byoc_result_envelope(payload, tenant_id)
        outcome = adapter.submit_result(
            tenant_id=tenant_id,
            worker_token=body.worker_token,
            request_nonce=body.request_nonce,
            result=envelope,
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return ByocSubmitResultResponse(
        tenant_id=tenant_id,
        backend_id=adapter.backend_id,
        accepted=outcome.accepted,
        duplicate=outcome.duplicate,
        reason_code=outcome.reason_code,
    )


@router.post(
    "/{tenant_id}/admin/byoc/webhook/jobs/submit",
    response_model=ByocSubmitResultResponse,
)
async def submit_byoc_webhook_job_result(
    tenant_id: str,
    body: ByocWebhookSubmitResultRequest,
    ctx: TenantRuntimeContext = Depends(get_tenant_context),
    _identity: IdentityContext = Depends(require_valid_identity),
) -> ByocSubmitResultResponse:
    adapter = _resolve_byoc_adapter(ctx)
    payload = body.result or {}
    try:
        envelope = _to_byoc_result_envelope(payload, tenant_id)
        outcome = adapter.submit_result_webhook(
            tenant_id=tenant_id,
            webhook_secret=body.webhook_secret,
            webhook_request_id=body.webhook_request_id,
            result=envelope,
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return ByocSubmitResultResponse(
        tenant_id=tenant_id,
        backend_id=adapter.backend_id,
        accepted=outcome.accepted,
        duplicate=outcome.duplicate,
        reason_code=outcome.reason_code,
    )


@router.post(
    "/{tenant_id}/admin/byoc/cleanup",
    response_model=ByocCleanupResponse,
)
async def cleanup_byoc_runtime_retention(
    tenant_id: str,
    body: ByocCleanupRequest,
    ctx: TenantRuntimeContext = Depends(get_tenant_context),
    _identity: IdentityContext = Depends(require_valid_identity),
) -> ByocCleanupResponse:
    adapter = _resolve_byoc_adapter(ctx)
    cleanup_method = getattr(adapter, "cleanup_retention", None)
    stats: dict[str, int] = {}
    if callable(cleanup_method):
        stats = cleanup_method(tenant_id=tenant_id, force=body.force)
    return ByocCleanupResponse(
        tenant_id=tenant_id,
        backend_id=adapter.backend_id,
        cleanup_stats=stats,
    )
