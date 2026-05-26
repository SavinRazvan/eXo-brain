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

from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from src.api.dependencies import get_app_modules, get_tenant_context, require_valid_identity
from src.api.middleware.entitlements import (
    EntitlementDecision,
    emit_entitlement_decision_event,
    evaluate_feature_entitlement,
)
from src.api.schemas.runtime_control_schemas import (
    ByocCleanupRequest,
    ByocCleanupResponse,
    ByocClaimJobRequest,
    ByocClaimJobResponse,
    ByocDlqListResponse,
    ByocDlqReplayBulkRequest,
    ByocDlqReplayBulkResponse,
    ByocDlqReplayFailure,
    ByocDlqRecord,
    ByocDlqReplayResponse,
    ByocGovernanceAnomaly,
    ByocGovernanceAnomalyReport,
    ByocGovernanceConflictCount,
    ByocGovernanceCostMetrics,
    ByocGovernanceMetricsResponse,
    ByocGovernanceReasonCount,
    ByocGovernanceSubmissionMetrics,
    ByocSubmitResultRequest,
    ByocSubmitResultResponse,
    ByocWebhookSubmitResultRequest,
    ByocWorkerTokenRequest,
    ByocWorkerTokenResponse,
    RuntimeCancellationRequest,
    RuntimeCancellationResponse,
    RuntimeCleanupEventsResponse,
    RuntimeControlStatsResponse,
    RuntimeIngressBudgetSummaryResponse,
    RuntimeRunCancelResponse,
    RuntimeRunListResponse,
    RuntimeRunRecord,
)
from src.core.run_control_registry import RunControlRegistry
from src.identity.contracts import IdentityContext
from src.policies.entitlements import EntitledFeature
from src.policies.governance_anomaly_detector import (
    GovernanceAnomalyThresholds,
    detect_governance_anomalies,
)
from src.runtime.tenant_runtime import TenantRuntimeContext
from src.tools.byoc.job_contracts import ByocToolResultEnvelope
from src.schemas.tool_io import PolicyAction

router = APIRouter(tags=["runtime-control"])


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _entitlement_http_exception(decision: EntitlementDecision) -> HTTPException:
    return HTTPException(
        status_code=403,
        detail=f"{decision.reason_code}: {decision.message}",
    )


def _request_route_label(request: Request) -> str:
    route = request.scope.get("route")
    route_path = getattr(route, "path", request.url.path)
    return f"{request.method.upper()} {route_path}"


async def _enforce_feature_entitlement(
    *,
    request: Request,
    tenant_id: str,
    identity: IdentityContext,
    feature: EntitledFeature,
    surface: str,
) -> None:
    decision = evaluate_feature_entitlement(identity=identity, feature=feature)
    correlation_id = f"entitlement_{uuid.uuid4().hex[:8]}"
    modules = get_app_modules(request)
    if modules is None:
        raise HTTPException(status_code=503, detail="Application modules are not configured.")
    audit_pipeline = modules.audit_observability.tool_audit_pipeline
    await emit_entitlement_decision_event(
        audit_pipeline=audit_pipeline,
        correlation_id=correlation_id,
        tenant_id=tenant_id,
        surface=surface,
        route=_request_route_label(request),
        decision=decision,
    )
    if decision.decision != PolicyAction.ALLOW:
        raise _entitlement_http_exception(decision)


async def _require_runtime_admin_entitlement(
    request: Request,
    tenant_id: str,
    identity: IdentityContext = Depends(require_valid_identity),
) -> IdentityContext:
    await _enforce_feature_entitlement(
        request=request,
        tenant_id=tenant_id,
        identity=identity,
        feature=EntitledFeature.GOVERNANCE_RUNTIME_ADMIN_CONTROLS,
        surface="runtime_control_admin",
    )
    return identity


async def _require_byoc_governance_metrics_entitlement(
    request: Request,
    tenant_id: str,
    identity: IdentityContext = Depends(require_valid_identity),
) -> IdentityContext:
    await _enforce_feature_entitlement(
        request=request,
        tenant_id=tenant_id,
        identity=identity,
        feature=EntitledFeature.GOVERNANCE_BYOC_GOVERNANCE_ANALYTICS,
        surface="byoc_governance_metrics",
    )
    return identity


def _resolve_runtime_adapter(ctx: TenantRuntimeContext):
    adapter = ctx.tool_executor.execution_adapter()
    if adapter is None:
        raise HTTPException(
            status_code=409,
            detail="Hosted runtime adapter is not enabled for this tenant.",
        )
    return adapter


def _resolve_run_registry(request: Request) -> RunControlRegistry:
    modules = get_app_modules(request)
    registry = modules.session_runtime.run_control_registry if modules is not None else None
    if registry is None:
        raise HTTPException(status_code=503, detail="Run control registry is not configured on this server.")
    return registry


def _resolve_ingress_budget_recorder(request: Request):
    modules = get_app_modules(request)
    if modules is None:
        return None
    return modules.audit_observability.ingress_budget_recorder


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
    _identity: IdentityContext = Depends(_require_runtime_admin_entitlement),
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
    _identity: IdentityContext = Depends(_require_runtime_admin_entitlement),
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
    _identity: IdentityContext = Depends(_require_runtime_admin_entitlement),
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
    _identity: IdentityContext = Depends(_require_runtime_admin_entitlement),
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
    _identity: IdentityContext = Depends(_require_runtime_admin_entitlement),
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
    _identity: IdentityContext = Depends(_require_runtime_admin_entitlement),
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
    _identity: IdentityContext = Depends(_require_runtime_admin_entitlement),
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
    _identity: IdentityContext = Depends(_require_runtime_admin_entitlement),
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
    _identity: IdentityContext = Depends(_require_runtime_admin_entitlement),
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
    _identity: IdentityContext = Depends(_require_runtime_admin_entitlement),
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
    _identity: IdentityContext = Depends(_require_runtime_admin_entitlement),
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
    _identity: IdentityContext = Depends(_require_runtime_admin_entitlement),
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


@router.get(
    "/{tenant_id}/admin/byoc/dlq",
    response_model=ByocDlqListResponse,
)
async def list_byoc_dead_letter_jobs(
    tenant_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    ctx: TenantRuntimeContext = Depends(get_tenant_context),
    _identity: IdentityContext = Depends(_require_runtime_admin_entitlement),
) -> ByocDlqListResponse:
    adapter = _resolve_byoc_adapter(ctx)
    list_method = getattr(adapter, "list_dead_letter_jobs", None)
    records: list[dict[str, str]] = []
    if callable(list_method):
        records = list_method(tenant_id=tenant_id, limit=limit)
    return ByocDlqListResponse(
        tenant_id=tenant_id,
        backend_id=adapter.backend_id,
        total=len(records),
        records=[ByocDlqRecord.model_validate(item) for item in records],
    )


@router.post(
    "/{tenant_id}/admin/byoc/dlq/{job_id}/replay",
    response_model=ByocDlqReplayResponse,
)
async def replay_byoc_dead_letter_job(
    tenant_id: str,
    job_id: str,
    ctx: TenantRuntimeContext = Depends(get_tenant_context),
    _identity: IdentityContext = Depends(_require_runtime_admin_entitlement),
) -> ByocDlqReplayResponse:
    adapter = _resolve_byoc_adapter(ctx)
    replay_method = getattr(adapter, "replay_dead_letter_job", None)
    replayed = False
    if callable(replay_method):
        replayed = bool(replay_method(tenant_id=tenant_id, job_id=job_id))
    return ByocDlqReplayResponse(
        tenant_id=tenant_id,
        backend_id=adapter.backend_id,
        job_id=job_id,
        replayed=replayed,
    )


@router.post(
    "/{tenant_id}/admin/byoc/dlq/replay",
    response_model=ByocDlqReplayBulkResponse,
)
async def replay_byoc_dead_letter_jobs_bulk(
    tenant_id: str,
    body: ByocDlqReplayBulkRequest,
    ctx: TenantRuntimeContext = Depends(get_tenant_context),
    _identity: IdentityContext = Depends(_require_runtime_admin_entitlement),
) -> ByocDlqReplayBulkResponse:
    adapter = _resolve_byoc_adapter(ctx)
    list_method = getattr(adapter, "list_dead_letter_jobs", None)
    replay_bulk_method = getattr(adapter, "replay_dead_letter_jobs", None)
    replay_single_method = getattr(adapter, "replay_dead_letter_job", None)
    bounded_limit = max(1, min(int(body.limit), 500))

    requested_ids = [str(item).strip() for item in body.job_ids if str(item).strip()]
    if requested_ids:
        target_job_ids = list(dict.fromkeys(requested_ids))[:bounded_limit]
    else:
        records = list_method(tenant_id=tenant_id, limit=bounded_limit) if callable(list_method) else []
        target_job_ids = [str(item.get("job_id", "")).strip() for item in records if str(item.get("job_id", "")).strip()]

    attempted = len(target_job_ids)
    replayed = 0
    failures: list[ByocDlqReplayFailure] = []
    if attempted == 0:
        return ByocDlqReplayBulkResponse(
            tenant_id=tenant_id,
            backend_id=adapter.backend_id,
            attempted=0,
            replayed=0,
            failed=0,
            failures=[],
        )

    if callable(replay_bulk_method):
        summary = replay_bulk_method(tenant_id=tenant_id, job_ids=target_job_ids, limit=bounded_limit)
        attempted = int(summary.get("attempted", attempted))
        replayed = int(summary.get("replayed", 0))
        raw_failures = summary.get("failures", [])
        if isinstance(raw_failures, list):
            for item in raw_failures:
                if not isinstance(item, dict):
                    continue
                job_id = str(item.get("job_id", "")).strip()
                reason_code = str(item.get("reason_code", "")).strip() or "DLQ_REPLAY_REJECTED"
                if job_id:
                    failures.append(ByocDlqReplayFailure(job_id=job_id, reason_code=reason_code))
    elif callable(replay_single_method):
        for job_id in target_job_ids:
            if replay_single_method(tenant_id=tenant_id, job_id=job_id):
                replayed += 1
            else:
                failures.append(
                    ByocDlqReplayFailure(
                        job_id=job_id,
                        reason_code="DLQ_REPLAY_NOT_FOUND_OR_NOT_DLQ",
                    )
                )

    return ByocDlqReplayBulkResponse(
        tenant_id=tenant_id,
        backend_id=adapter.backend_id,
        attempted=attempted,
        replayed=replayed,
        failed=max(attempted - replayed, 0),
        failures=failures,
    )


@router.get(
    "/{tenant_id}/admin/byoc/governance-metrics",
    response_model=ByocGovernanceMetricsResponse,
)
async def get_byoc_governance_metrics(
    tenant_id: str,
    request: Request,
    ctx: TenantRuntimeContext = Depends(get_tenant_context),
    _identity: IdentityContext = Depends(_require_byoc_governance_metrics_entitlement),
) -> ByocGovernanceMetricsResponse:
    modules = get_app_modules(request)
    if modules is None:
        raise HTTPException(status_code=503, detail="Application modules are not configured.")

    adapter = _resolve_byoc_adapter(ctx)
    stats_method = getattr(adapter, "control_stats_for_tenant", None)
    control_stats = adapter.control_stats()
    if callable(stats_method):
        control_stats = stats_method(tenant_id=tenant_id)

    window_policy_enabled = bool(int(control_stats.get("tenant_cost_window_policy_enabled", 0)))
    window_seconds = int(control_stats.get("tenant_cost_window_seconds", 0))
    window_started_epoch = int(control_stats.get("tenant_cost_window_started_epoch", 0))
    lifetime_cost_total = int(control_stats.get("tenant_cost_microunits_total", 0))
    window_cost_total = int(control_stats.get("tenant_cost_window_microunits", lifetime_cost_total))
    cost_total = window_cost_total if window_policy_enabled else lifetime_cost_total
    cost_limit = int(control_stats.get("tenant_cost_limit_microunits", 0))
    cost_remaining = int(
        control_stats.get(
            "tenant_cost_window_remaining_microunits" if window_policy_enabled else "tenant_cost_remaining_microunits",
            max(cost_limit - cost_total, 0),
        )
    )
    submit_attempts = int(control_stats.get("tenant_submit_attempts_total", 0))
    rejected_total = int(control_stats.get("tenant_rejected_results_total", 0))
    utilization_ratio = float(cost_total / cost_limit) if cost_limit > 0 else 0.0
    rejection_rate = float(rejected_total / submit_attempts) if submit_attempts > 0 else 0.0

    reasons: list[ByocGovernanceReasonCount] = []
    for key, value in control_stats.items():
        if not key.startswith("tenant_rejected_reason_"):
            continue
        reason_code = key.removeprefix("tenant_rejected_reason_")
        reasons.append(ByocGovernanceReasonCount(reason_code=reason_code, count=int(value)))
    reasons.sort(key=lambda item: (-item.count, item.reason_code))
    reason_counts = {item.reason_code: item.count for item in reasons}
    conflict_counts: list[ByocGovernanceConflictCount] = []
    conflict_method = getattr(adapter, "conflict_counts_for_tenant", None)
    if callable(conflict_method):
        raw_conflicts = conflict_method(tenant_id=tenant_id)
        for record in raw_conflicts:
            conflict_counts.append(
                ByocGovernanceConflictCount(
                    strategy=str(record.strategy),
                    tool_name=str(record.tool_name),
                    tool_version=str(record.tool_version),
                    reason_code=str(record.reason_code),
                    count=int(record.count),
                )
            )

    settings = modules.platform_bootstrap.settings
    anomaly_enabled = bool(settings.runtime.byoc_anomaly_detection_enabled)
    anomaly_thresholds = GovernanceAnomalyThresholds(
        cost_utilization_threshold=float(settings.runtime.byoc_anomaly_cost_utilization_threshold),
        rejection_rate_threshold=float(settings.runtime.byoc_anomaly_rejection_rate_threshold),
        reason_share_threshold=float(settings.runtime.byoc_anomaly_reason_share_threshold),
        min_submit_attempts=int(settings.runtime.byoc_anomaly_min_submit_attempts),
        min_rejection_count=int(settings.runtime.byoc_anomaly_min_rejection_count),
    )
    anomalies = []
    if anomaly_enabled:
        anomalies = detect_governance_anomalies(
            cost_utilization_ratio=utilization_ratio,
            rejection_rate=rejection_rate,
            submit_attempts_total=submit_attempts,
            rejected_results_total=rejected_total,
            rejection_reason_counts=reason_counts,
            thresholds=anomaly_thresholds,
        )

    return ByocGovernanceMetricsResponse(
        tenant_id=tenant_id,
        backend_id=adapter.backend_id,
        generated_at_utc=_utc_now(),
        cost=ByocGovernanceCostMetrics(
            window="windowed" if window_policy_enabled else "lifetime",
            window_seconds=window_seconds if window_policy_enabled else 0,
            window_started_at_epoch=window_started_epoch if window_policy_enabled else 0,
            cost_microunits_total=cost_total,
            cost_limit_microunits=cost_limit,
            cost_remaining_microunits=max(cost_remaining, 0),
            utilization_ratio=utilization_ratio,
        ),
        submissions=ByocGovernanceSubmissionMetrics(
            submit_attempts_total=submit_attempts,
            rejected_results_total=rejected_total,
            rejection_rate=rejection_rate,
        ),
        rejection_reasons=reasons,
        conflict_counts=conflict_counts,
        anomaly_report=ByocGovernanceAnomalyReport(
            enabled=anomaly_enabled,
            advisory_only=True,
            min_submit_attempts=anomaly_thresholds.min_submit_attempts,
            min_rejection_count=anomaly_thresholds.min_rejection_count,
            anomalies=[
                ByocGovernanceAnomaly(
                    code=item.code,
                    severity=item.severity,
                    message=item.message,
                    value=item.value,
                    threshold=item.threshold,
                    reason_code=item.reason_code,
                )
                for item in anomalies
            ],
        ),
    )


@router.get(
    "/{tenant_id}/admin/runtime/ingress-budget",
    response_model=RuntimeIngressBudgetSummaryResponse,
)
async def get_runtime_ingress_budget_summary(
    tenant_id: str,
    request: Request,
    _ctx: TenantRuntimeContext = Depends(get_tenant_context),
    _identity: IdentityContext = Depends(_require_runtime_admin_entitlement),
) -> RuntimeIngressBudgetSummaryResponse:
    recorder = _resolve_ingress_budget_recorder(request)
    raw_summary = recorder.summary(tenant_id=tenant_id) if recorder is not None else {}
    summary = {
        "samples": int(raw_summary.get("samples", 0)),
        "p95_latency_ms": float(raw_summary.get("p95_latency_ms", 0.0)),
        "timeout_total": int(raw_summary.get("timeout_total", 0)),
        "timeout_rate": float(raw_summary.get("timeout_rate", 0.0)),
        "budget_exceeded_total": int(raw_summary.get("budget_exceeded_total", 0)),
    }
    raw_profiles = raw_summary.get("profiles", {})
    profiles: dict[str, dict[str, float | int]] = {}
    if isinstance(raw_profiles, dict):
        for profile_name, profile_summary in raw_profiles.items():
            if not isinstance(profile_summary, dict):
                continue
            normalized_profile = str(profile_name).strip().lower()
            if not normalized_profile:
                continue
            profiles[normalized_profile] = {
                "samples": int(profile_summary.get("samples", 0)),
                "p95_latency_ms": float(profile_summary.get("p95_latency_ms", 0.0)),
                "timeout_total": int(profile_summary.get("timeout_total", 0)),
                "timeout_rate": float(profile_summary.get("timeout_rate", 0.0)),
                "budget_exceeded_total": int(profile_summary.get("budget_exceeded_total", 0)),
            }
    return RuntimeIngressBudgetSummaryResponse(
        tenant_id=tenant_id,
        generated_at_utc=_utc_now(),
        summary=summary,
        profiles=profiles,
    )
