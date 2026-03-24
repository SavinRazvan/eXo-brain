"""
File: turns.py
Path: src/api/routers/turns.py
Role: Turn execution endpoints — SSE streaming and WebSocket for agent conversations.
Used By:
 - src/api/app.py
Depends On:
 - src/api/dependencies.py
 - src/api/schemas/turn_schemas.py
 - src/runtime/tenant_runtime.py
 - src/integration/host_adapter.py
 - src/schemas/events.py
 - sse_starlette
Notes:
 - Both SSE and WebSocket emit the same JSON event envelope (defined in turn_schemas.py).
 - SSE: stateless, one turn per HTTP request. Best for scripts, notebooks, curl clients.
 - WebSocket: persistent, multi-turn, supports mid-session cancellation via asyncio.Task.
 - RuntimeEvent types are mapped to the shared EventEnvelope format.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from sse_starlette.sse import EventSourceResponse

from src.api.dependencies import get_app_modules, get_tenant_context, require_tenant_scope_identity
from src.api.middleware.auth import extract_identity, is_identity_usable
from src.api.middleware.entitlements import (
    EntitlementDecision,
    emit_entitlement_decision_event,
    evaluate_feature_entitlement,
    required_feature_for_governance_overlay,
)
from src.api.schemas.turn_schemas import TurnSubmitRequest
from src.core.session_context import SessionContext
from src.identity.contracts import IdentityContext
from src.observability.ingress_budget import (
    DEFAULT_INGRESS_PROFILE,
    IngressBudgetConfig,
    budget_config_from_policy_settings,
    evaluate_with_budget,
)
from src.policies.ingress_gates import (
    IngressDecision,
    IngressTurnContext,
    build_ingress_gate_chain_from_overlay,
)
from src.runtime.tenant_runtime import TenantRuntimeContext
from src.schemas.events import RuntimeEvent, RuntimeEventType
from src.schemas.tool_io import PolicyAction
from src.modules.platform_bootstrap.service import app_modules_from_requestlike

router = APIRouter(tags=["turns"])


def _get_factory(request: Request):
    modules = get_app_modules(request)
    if modules is None:
        raise HTTPException(status_code=503, detail="Session runtime module is not configured.")
    return modules.session_runtime.tenant_factory


def _get_run_registry(request: Request):
    modules = get_app_modules(request)
    if modules is None:
        raise HTTPException(status_code=503, detail="Session runtime module is not configured.")
    return modules.session_runtime.run_control_registry


def _get_tenant_policy_overlay(app, tenant_id: str) -> dict[str, Any]:
    modules = app_modules_from_requestlike(app)
    if modules is None:
        return {}
    return modules.tenant_governance.overlay_for_tenant(tenant_id)


def _build_ingress_gate_chain(overlay: dict[str, Any]):
    return build_ingress_gate_chain_from_overlay(overlay)


def _ingress_config_invalid_decision(message: str) -> IngressDecision:
    return IngressDecision(
        schema_version="1.0",
        decision=PolicyAction.DENY,
        reason_code="INGRESS_PROFILE_CONFIG_INVALID",
        message=message,
        gate_id="ingress-profile-config",
        gate_version="1.0.0",
    )


def _entitlement_error_event(decision: EntitlementDecision, correlation_id: str) -> dict[str, Any]:
    return {
        "event": "error",
        "code": decision.reason_code,
        "message": decision.message,
        "correlation_id": correlation_id,
        "feature": decision.feature.value,
        "required_tier": decision.required_tier.value,
        "current_tier": decision.current_tier.value,
    }


def _entitlement_http_exception(decision: EntitlementDecision) -> HTTPException:
    return HTTPException(
        status_code=403,
        detail=f"{decision.reason_code}: {decision.message}",
    )


def _ingress_error_event(decision: IngressDecision, correlation_id: str) -> dict[str, Any]:
    return {
        "event": "error",
        "code": decision.reason_code,
        "message": decision.message,
        "correlation_id": correlation_id,
        "review_required": decision.review_required,
        "review_channel": decision.review_channel,
    }


def _ingress_http_exception(decision: IngressDecision) -> HTTPException:
    return HTTPException(
        status_code=403,
        detail=f"{decision.reason_code}: {decision.message}",
    )


async def _evaluate_ingress_turn(
    *,
    gate_chain,
    budget_config: IngressBudgetConfig,
    tenant_id: str,
    session_id: str,
    correlation_id: str,
    transport: str,
    user_input: str,
    identity: IdentityContext,
    budget_recorder,
    audit_pipeline,
) -> IngressDecision:
    policy_metadata_fn = getattr(gate_chain, "policy_metadata", None)
    policy_metadata: dict[str, Any] = {}
    if callable(policy_metadata_fn):
        policy_metadata = dict(policy_metadata_fn())
    ingress_profile = str(policy_metadata.get("ingress_profile", DEFAULT_INGRESS_PROFILE)).strip().lower()
    if not ingress_profile:
        ingress_profile = DEFAULT_INGRESS_PROFILE

    async def _evaluate_gate_chain() -> IngressDecision:
        return gate_chain.evaluate(
            IngressTurnContext(
                tenant_id=tenant_id,
                session_id=session_id,
                correlation_id=correlation_id,
                transport=transport,
                user_input=user_input,
                identity_subject=identity.subject,
                identity_roles=list(identity.roles),
                identity_tenant_id=identity.tenant_id,
            )
        )
    decision, observation = await evaluate_with_budget(
        evaluate=_evaluate_gate_chain,
        config=budget_config,
        profile_name=ingress_profile,
    )
    if budget_recorder is not None:
        budget_recorder.observe(tenant_id=tenant_id, observation=observation)
    if audit_pipeline is not None:
        await audit_pipeline.emit(
            event_type="turn_ingress_decision",
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            payload={
                "session_id": session_id,
                "transport": transport,
                "input_chars": len(user_input),
                **policy_metadata,
                **observation.to_payload(),
                **decision.to_payload(),
            },
        )
        if decision.classifier_mode:
            await audit_pipeline.emit(
                event_type="turn_ingress_classifier_telemetry",
                correlation_id=correlation_id,
                tenant_id=tenant_id,
                payload={
                    "session_id": session_id,
                    "transport": transport,
                    "input_chars": len(user_input),
                    **policy_metadata,
                    **decision.to_payload(),
                },
            )
        if decision.signed_plugin_ref:
            await audit_pipeline.emit(
                event_type="turn_ingress_signed_plugin_telemetry",
                correlation_id=correlation_id,
                tenant_id=tenant_id,
                payload={
                    "session_id": session_id,
                    "transport": transport,
                    "input_chars": len(user_input),
                    **policy_metadata,
                    **decision.to_payload(),
                },
            )
        if observation.budget_exceeded or observation.timed_out:
            await audit_pipeline.emit(
                event_type="turn_ingress_budget_alert",
                correlation_id=correlation_id,
                tenant_id=tenant_id,
                payload={
                    "session_id": session_id,
                    "transport": transport,
                    "input_chars": len(user_input),
                    **policy_metadata,
                    **observation.to_payload(),
                    **decision.to_payload(),
                },
            )
    return decision


async def _evaluate_governance_entitlement(
    *,
    tenant_id: str,
    session_id: str,
    correlation_id: str,
    transport: str,
    identity: IdentityContext,
    overlay: dict[str, Any],
    audit_pipeline,
) -> EntitlementDecision:
    feature = required_feature_for_governance_overlay(overlay)
    decision = evaluate_feature_entitlement(identity=identity, feature=feature)
    await emit_entitlement_decision_event(
        audit_pipeline=audit_pipeline,
        correlation_id=correlation_id,
        tenant_id=tenant_id,
        surface="turn_ingress",
        route=f"{transport}_turn_entry",
        decision=decision,
        extra_payload={
            "session_id": session_id,
            "transport": transport,
        },
    )
    return decision


def _websocket_cross_tenant_admin_allowed(websocket: WebSocket, identity: IdentityContext) -> bool:
    path = str(getattr(websocket.url, "path", "")).strip()
    if "/tenants/" not in path or "/admin/" not in path:
        return False
    modules = app_modules_from_requestlike(websocket)
    if modules is None:
        return False
    return modules.identity_access.service.allow_cross_tenant_admin_access(identity)


def _forward_runtime_cancellations(
    execution_adapter,
    call_ids: set[str],
    *,
    terminal_event_seen: bool,
) -> int:
    """Best-effort forwarding of call-id cancellations to hosted runtime adapter."""
    if execution_adapter is None or terminal_event_seen:
        return 0
    forwarded = 0
    for call_id in sorted(call_ids):
        if execution_adapter.request_cancellation(call_id):
            forwarded += 1
    return forwarded


def _mark_cancelled_if_running(run_registry, *, tenant_id: str, run_id: str, terminal_event: str) -> None:
    record = run_registry.get_run(tenant_id=tenant_id, run_id=run_id)
    if record is None:
        return
    status = str(record.get("status", ""))
    if status in {"completed", "errored", "cancelled"}:
        return
    run_registry.mark_terminal(
        tenant_id=tenant_id,
        run_id=run_id,
        status="cancelled",
        terminal_event=terminal_event,
    )


def _build_cancelled_progress_events(
    *,
    call_id_to_tool_name: dict[str, str],
    correlation_id: str,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for call_id in sorted(str(key).strip() for key in call_id_to_tool_name.keys() if str(key).strip()):
        events.append(
            {
                "event": "tool_progress",
                "call_id": call_id,
                "tool_name": str(call_id_to_tool_name.get(call_id, "")),
                "state": "cancelled",
                "tool_status": "cancelled",
                "error_code": "CANCEL_REQUESTED",
                "job_id": "",
                "lease_token": "",
                "lease_expires_at_epoch": "",
                "claim_attempt": "",
                "correlation_id": correlation_id,
            }
        )
    return events


def _runtime_event_to_dict(event: RuntimeEvent) -> dict[str, Any]:
    """Map a RuntimeEvent to the shared JSON event envelope."""
    if event.event_type == RuntimeEventType.OUTPUT_DELTA:
        return {
            "event": "output_delta",
            "delta": event.payload.get("text", ""),
            "correlation_id": event.correlation_id,
        }
    elif event.event_type == RuntimeEventType.TOOL_INTENT:
        call = event.tool_call
        return {
            "event": "tool_call",
            "call_id": call.call_id if call else "",
            "tool_name": call.tool_name if call else "",
            "arguments": dict(call.arguments) if call else {},
            "correlation_id": event.correlation_id,
        }
    elif event.event_type == RuntimeEventType.TOOL_PROGRESS:
        return {
            "event": "tool_progress",
            "call_id": str(event.payload.get("call_id", "")),
            "tool_name": str(event.payload.get("tool_name", "")),
            "state": str(event.payload.get("state", "")),
            "tool_status": str(event.payload.get("tool_status", "")),
            "error_code": str(event.payload.get("error_code", "")),
            "job_id": str(event.payload.get("job_id", "")),
            "lease_token": str(event.payload.get("lease_token", "")),
            "lease_expires_at_epoch": str(event.payload.get("lease_expires_at_epoch", "")),
            "claim_attempt": str(event.payload.get("claim_attempt", "")),
            "correlation_id": event.correlation_id,
        }
    elif event.event_type == RuntimeEventType.RUN_COMPLETE:
        return {
            "event": "run_complete",
            "run_id": event.run_id,
            "output": event.payload,
            "correlation_id": event.correlation_id,
        }
    elif event.event_type == RuntimeEventType.ERROR:
        return {
            "event": "error",
            "code": event.payload.get("code", "UNKNOWN_ERROR"),
            "message": event.payload.get("message", ""),
            "correlation_id": event.correlation_id,
        }
    # Fallback — emit as raw payload
    return {
        "event": event.event_type.value,
        "payload": event.payload,
        "correlation_id": event.correlation_id,
    }


async def _stream_turn(
    tenant_id: str,
    session_id: str,
    user_input: str,
    correlation_id: str,
    ingress_decision: IngressDecision | None,
    factory,
    ctx: TenantRuntimeContext,
    identity: IdentityContext,
) -> AsyncIterator[dict[str, Any]]:
    """Shared generator that yields event dicts from a single agent turn."""
    try:
        host_adapter = factory.get_session_runtime(session_id)
    except KeyError:
        yield {"event": "error", "code": "SESSION_NOT_FOUND",
               "message": f"Session '{session_id}' not found", "correlation_id": correlation_id}
        return

    run_id = f"run_{uuid.uuid4().hex[:8]}"
    session_metadata: dict[str, Any] = {}
    if ingress_decision is not None:
        session_metadata["ingress_decision"] = ingress_decision.to_payload()
    session_ctx = SessionContext(
        session_id=session_id,
        run_id=run_id,
        job_id=f"job_{uuid.uuid4().hex[:8]}",
        task_id=f"task_{uuid.uuid4().hex[:8]}",
        agent_id=session_id,
        provider_id="api",
        correlation_id=correlation_id or run_id,
        identity=identity,
        metadata=session_metadata,
    )

    try:
        async for event in host_adapter.submit_turn(session_ctx, user_input):
            yield _runtime_event_to_dict(event)
    except Exception as exc:
        yield {
            "event": "error",
            "code": "TURN_EXECUTION_ERROR",
            "message": str(exc),
            "correlation_id": correlation_id,
        }


# ---------------------------------------------------------------------------
# SSE turn endpoint
# ---------------------------------------------------------------------------


@router.post("/{tenant_id}/sessions/{session_id}/turns")
async def submit_turn_sse(
    tenant_id: str,
    session_id: str,
    body: TurnSubmitRequest,
    request: Request,
    ctx: TenantRuntimeContext = Depends(get_tenant_context),
    identity: IdentityContext = Depends(require_tenant_scope_identity),
) -> EventSourceResponse:
    """Submit a single agent turn and stream runtime events as SSE.

    Returns 404 if the session is not found.
    Events: output_delta, tool_call, run_complete, error.
    """
    factory = _get_factory(request)

    # Verify session exists before opening SSE stream
    try:
        factory.get_session_runtime(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    correlation_id = body.correlation_id or f"corr_{uuid.uuid4().hex[:8]}"
    execution_adapter = ctx.tool_executor.execution_adapter()
    run_id = correlation_id
    run_registry = _get_run_registry(request)
    modules = get_app_modules(request)
    if modules is None:
        raise HTTPException(status_code=503, detail="Application modules are not configured.")
    turn_rate_limiter = modules.tenant_governance.turn_rate_limiter
    audit_pipeline = modules.audit_observability.tool_audit_pipeline
    budget_recorder = modules.audit_observability.ingress_budget_recorder
    settings = modules.platform_bootstrap.settings
    budget_config = budget_config_from_policy_settings(settings.policy)
    policy_overlay = _get_tenant_policy_overlay(request.app, tenant_id)
    entitlement_decision = await _evaluate_governance_entitlement(
        tenant_id=tenant_id,
        session_id=session_id,
        correlation_id=correlation_id,
        transport="sse",
        identity=identity,
        overlay=policy_overlay,
        audit_pipeline=audit_pipeline,
    )
    if entitlement_decision.decision != PolicyAction.ALLOW:
        raise _entitlement_http_exception(entitlement_decision)
    try:
        ingress_gate_chain = _build_ingress_gate_chain(policy_overlay)
    except ValueError as exc:
        ingress_decision = _ingress_config_invalid_decision(str(exc))
        if audit_pipeline is not None:
            await audit_pipeline.emit(
                event_type="turn_ingress_decision",
                correlation_id=correlation_id,
                tenant_id=tenant_id,
                payload={
                    "session_id": session_id,
                    "transport": "sse",
                    "input_chars": len(body.input),
                    "ingress_profile": "invalid",
                    "ingress_custom_rule_count": 0,
                    "ingress_custom_rule_ids": [],
                    "ingress_profile_compatibility_mode": "strict",
                    "ingress_classifier_mode": "off",
                    "ingress_classifier_threshold": 0.0,
                    "ingress_classifier_model_version": "",
                    "ingress_classifier_signal_count": 0,
                    "signed_gate_plugin_ref": "",
                    "signed_gate_plugin_version": "",
                    "signed_gate_plugin_signer": "",
                    "signed_gate_plugin_sandbox_mode": "",
                    "signed_gate_plugin_rule_count": 0,
                    **ingress_decision.to_payload(),
                },
            )
        raise _ingress_http_exception(ingress_decision) from exc
    ingress_decision = await _evaluate_ingress_turn(
        gate_chain=ingress_gate_chain,
        budget_config=budget_config,
        tenant_id=tenant_id,
        session_id=session_id,
        correlation_id=correlation_id,
        transport="sse",
        user_input=body.input,
        identity=identity,
        budget_recorder=budget_recorder,
        audit_pipeline=audit_pipeline,
    )
    if ingress_decision.decision != PolicyAction.ALLOW:
        raise _ingress_http_exception(ingress_decision)
    if turn_rate_limiter is not None:
        allowed, retry_after_seconds = turn_rate_limiter.allow(tenant_id)
        if not allowed:
            if audit_pipeline is not None:
                await audit_pipeline.emit(
                    event_type="turn_rejected_rate_limit",
                    correlation_id=correlation_id,
                    tenant_id=tenant_id,
                    payload={
                        "runtime_id": "sse",
                        "session_id": session_id,
                        "retry_after_seconds": retry_after_seconds,
                    },
                )
            raise HTTPException(
                status_code=429,
                detail=(
                    "TENANT_TURN_RATE_LIMIT_EXCEEDED: too many turn requests in the current window "
                    f"(retry_after_seconds={retry_after_seconds})"
                ),
            )
    max_active_runs = max(int(settings.limits.max_active_runs_per_tenant), 0)
    if max_active_runs > 0 and run_registry.count_active_runs(tenant_id=tenant_id) >= max_active_runs:
        if audit_pipeline is not None:
            await audit_pipeline.emit(
                event_type="turn_rejected_concurrency_limit",
                correlation_id=correlation_id,
                tenant_id=tenant_id,
                payload={"runtime_id": "sse", "session_id": session_id},
            )
        raise HTTPException(
            status_code=429,
            detail="TENANT_CONCURRENCY_LIMIT_EXCEEDED: too many active runs for this tenant",
        )
    run_registry.start_run(
        tenant_id=tenant_id,
        session_id=session_id,
        run_id=run_id,
        correlation_id=correlation_id,
        transport="sse",
    )

    async def event_generator():
        seen_call_id_to_tool_name: dict[str, str] = {}
        terminal_event_seen = False
        terminal_status = ""
        terminal_event = ""
        terminal_message = ""
        cancellation_progress_emitted = False
        try:
            async for event_dict in _stream_turn(
                tenant_id=tenant_id,
                session_id=session_id,
                user_input=body.input,
                correlation_id=correlation_id,
                ingress_decision=ingress_decision,
                factory=factory,
                ctx=ctx,
                identity=identity,
            ):
                if event_dict.get("event") in {"tool_call", "tool_progress"}:
                    call_id = str(event_dict.get("call_id", "")).strip()
                    if call_id:
                        seen_call_id_to_tool_name[call_id] = str(event_dict.get("tool_name", ""))
                        run_registry.record_tool_call(tenant_id=tenant_id, run_id=run_id, call_id=call_id)
                run_record = run_registry.get_run(tenant_id=tenant_id, run_id=run_id) or {}
                cancel_requested = bool(run_record.get("cancel_requested", False))
                if cancel_requested and not cancellation_progress_emitted and seen_call_id_to_tool_name:
                    cancellation_progress_emitted = True
                    for cancellation_event in _build_cancelled_progress_events(
                        call_id_to_tool_name=seen_call_id_to_tool_name,
                        correlation_id=correlation_id,
                    ):
                        yield {"data": json.dumps(cancellation_event)}
                    break
                if event_dict.get("event") in {"run_complete", "error"}:
                    terminal_event_seen = True
                    if event_dict.get("event") == "run_complete":
                        terminal_status = "completed"
                        terminal_event = "run_complete"
                    else:
                        terminal_status = "errored"
                        terminal_event = "error"
                        terminal_message = str(event_dict.get("message", ""))
                yield {"data": json.dumps(event_dict)}
        finally:
            forwarded = _forward_runtime_cancellations(
                execution_adapter=execution_adapter,
                call_ids=set(seen_call_id_to_tool_name.keys()),
                terminal_event_seen=terminal_event_seen,
            )
            run_record = run_registry.get_run(tenant_id=tenant_id, run_id=run_id) or {}
            cancel_requested = bool(run_record.get("cancel_requested", False))
            if forwarded > 0:
                run_registry.request_cancel(
                    tenant_id=tenant_id,
                    run_id=run_id,
                    reason="sse_stream_ended_before_terminal_event",
                )
            if terminal_event_seen:
                run_registry.mark_terminal(
                    tenant_id=tenant_id,
                    run_id=run_id,
                    status=terminal_status or "completed",
                    terminal_event=terminal_event or "run_complete",
                    terminal_message=terminal_message,
                )
            elif cancel_requested:
                run_registry.mark_terminal(
                    tenant_id=tenant_id,
                    run_id=run_id,
                    status="cancelled",
                    terminal_event="cancel_requested_stream_closed",
                )
            elif forwarded > 0:
                run_registry.mark_terminal(
                    tenant_id=tenant_id,
                    run_id=run_id,
                    status="cancelled",
                    terminal_event="cancel_forwarded",
                )
            else:
                run_registry.mark_terminal(
                    tenant_id=tenant_id,
                    run_id=run_id,
                    status="interrupted",
                    terminal_event="stream_closed",
                )

    return EventSourceResponse(event_generator())


# ---------------------------------------------------------------------------
# WebSocket turn endpoint
# ---------------------------------------------------------------------------


@router.websocket("/{tenant_id}/sessions/{session_id}/ws")
async def websocket_turn(
    tenant_id: str,
    session_id: str,
    websocket: WebSocket,
) -> None:
    """Persistent WebSocket connection for multi-turn agent conversations.

    Client message protocol:
      {"type": "turn", "input": "...", "run_id": "<optional>"}
      {"type": "cancel", "run_id": "..."}

    Server event protocol (same envelope as SSE):
      {"event": "output_delta", "delta": "...", "correlation_id": "..."}
      {"event": "tool_call", "tool_name": "...", "arguments": {...}, ...}
      {"event": "run_complete", "run_id": "...", "output": {...}, ...}
      {"event": "error", "code": "...", "message": "...", ...}
      {"event": "run_cancelled", "run_id": "..."}

    Cancellation: send {"type": "cancel", "run_id": "..."} to cancel a running turn.
    On disconnect: any in-flight turn task is automatically cancelled.
    """
    modules = app_modules_from_requestlike(websocket)
    if modules is None:
        await websocket.close(code=1011, reason="Application modules are not configured.")
        return
    factory = modules.session_runtime.tenant_factory
    ctx = factory.get_or_create(tenant_id)

    identity = await extract_identity(websocket)
    if identity is None or not is_identity_usable(identity):
        await websocket.close(code=4401, reason="Authentication required")
        return
    if str(identity.tenant_id).strip() != str(tenant_id).strip() and not _websocket_cross_tenant_admin_allowed(
        websocket, identity
    ):
        await websocket.close(code=4403, reason="TENANT_SCOPE_MISMATCH")
        return

    # Verify session exists before accepting WebSocket
    try:
        factory.get_session_runtime(session_id)
    except KeyError:
        await websocket.close(code=4404, reason=f"Session '{session_id}' not found")
        return

    await websocket.accept()

    # Map run_id → asyncio.Task for cancellation support
    active_tasks: dict[str, asyncio.Task] = {}
    # Map run_id → tool call_ids observed during stream for runtime cancellation forwarding.
    active_run_tool_calls: dict[str, dict[str, str]] = {}
    execution_adapter = ctx.tool_executor.execution_adapter()
    run_registry = modules.session_runtime.run_control_registry
    turn_rate_limiter = modules.tenant_governance.turn_rate_limiter
    audit_pipeline = modules.audit_observability.tool_audit_pipeline
    budget_recorder = modules.audit_observability.ingress_budget_recorder
    websocket_settings = modules.platform_bootstrap.settings
    budget_config = budget_config_from_policy_settings(websocket_settings.policy)

    async def run_turn_task(
        run_id: str,
        user_input: str,
        correlation_id: str,
        ingress_decision: IngressDecision,
    ) -> None:
        terminal_event_seen = False
        terminal_status = ""
        terminal_event = ""
        terminal_message = ""
        cancellation_progress_emitted = False
        try:
            async for event_dict in _stream_turn(
                tenant_id=tenant_id,
                session_id=session_id,
                user_input=user_input,
                correlation_id=correlation_id,
                ingress_decision=ingress_decision,
                factory=factory,
                ctx=ctx,
                identity=identity,
            ):
                if event_dict.get("event") in {"tool_call", "tool_progress"}:
                    call_id = str(event_dict.get("call_id", "")).strip()
                    if call_id:
                        active_run_tool_calls.setdefault(run_id, {})[call_id] = str(event_dict.get("tool_name", ""))
                        run_registry.record_tool_call(tenant_id=tenant_id, run_id=run_id, call_id=call_id)
                run_record = run_registry.get_run(tenant_id=tenant_id, run_id=run_id) or {}
                cancel_requested = bool(run_record.get("cancel_requested", False))
                if cancel_requested and not cancellation_progress_emitted:
                    cancellation_progress_emitted = True
                    call_id_to_tool_name = dict(active_run_tool_calls.get(run_id, {}))
                    for cancellation_event in _build_cancelled_progress_events(
                        call_id_to_tool_name=call_id_to_tool_name,
                        correlation_id=correlation_id,
                    ):
                        await websocket.send_json(cancellation_event)
                    _mark_cancelled_if_running(
                        run_registry,
                        tenant_id=tenant_id,
                        run_id=run_id,
                        terminal_event="cancel_requested_in_flight",
                    )
                    return
                if event_dict.get("event") in {"run_complete", "error"}:
                    terminal_event_seen = True
                    if event_dict.get("event") == "run_complete":
                        terminal_status = "completed"
                        terminal_event = "run_complete"
                    else:
                        terminal_status = "errored"
                        terminal_event = "error"
                        terminal_message = str(event_dict.get("message", ""))
                try:
                    await websocket.send_json(event_dict)
                except Exception:
                    return
        except asyncio.CancelledError:
            run_registry.mark_terminal(
                tenant_id=tenant_id,
                run_id=run_id,
                status="cancelled",
                terminal_event="ws_task_cancelled",
            )
            raise
        finally:
            active_tasks.pop(run_id, None)
            active_run_tool_calls.pop(run_id, None)
            if terminal_event_seen:
                run_registry.mark_terminal(
                    tenant_id=tenant_id,
                    run_id=run_id,
                    status=terminal_status or "completed",
                    terminal_event=terminal_event or "run_complete",
                    terminal_message=terminal_message,
                )

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json(
                    {"event": "error", "code": "INVALID_JSON", "message": "Message is not valid JSON"}
                )
                continue

            msg_type = msg.get("type", "")

            if msg_type == "turn":
                user_input = str(msg.get("input", "")).strip()
                if not user_input:
                    await websocket.send_json(
                        {"event": "error", "code": "EMPTY_INPUT", "message": "Turn input is empty"}
                    )
                    continue
                run_id = str(msg.get("run_id", "") or f"run_{uuid.uuid4().hex[:8]}")
                correlation_id = run_id
                policy_overlay = _get_tenant_policy_overlay(websocket.app, tenant_id)
                entitlement_decision = await _evaluate_governance_entitlement(
                    tenant_id=tenant_id,
                    session_id=session_id,
                    correlation_id=correlation_id,
                    transport="websocket",
                    identity=identity,
                    overlay=policy_overlay,
                    audit_pipeline=audit_pipeline,
                )
                if entitlement_decision.decision != PolicyAction.ALLOW:
                    await websocket.send_json(_entitlement_error_event(entitlement_decision, correlation_id))
                    continue
                try:
                    ingress_gate_chain = _build_ingress_gate_chain(policy_overlay)
                except ValueError as exc:
                    ingress_decision = _ingress_config_invalid_decision(str(exc))
                    if audit_pipeline is not None:
                        await audit_pipeline.emit(
                            event_type="turn_ingress_decision",
                            correlation_id=correlation_id,
                            tenant_id=tenant_id,
                            payload={
                                "session_id": session_id,
                                "transport": "websocket",
                                "input_chars": len(user_input),
                                "ingress_profile": "invalid",
                                "ingress_custom_rule_count": 0,
                                "ingress_custom_rule_ids": [],
                                "ingress_profile_compatibility_mode": "strict",
                                "ingress_classifier_mode": "off",
                                "ingress_classifier_threshold": 0.0,
                                "ingress_classifier_model_version": "",
                                "ingress_classifier_signal_count": 0,
                                "signed_gate_plugin_ref": "",
                                "signed_gate_plugin_version": "",
                                "signed_gate_plugin_signer": "",
                                "signed_gate_plugin_sandbox_mode": "",
                                "signed_gate_plugin_rule_count": 0,
                                **ingress_decision.to_payload(),
                            },
                        )
                    await websocket.send_json(_ingress_error_event(ingress_decision, correlation_id))
                    continue
                ingress_decision = await _evaluate_ingress_turn(
                    gate_chain=ingress_gate_chain,
                    budget_config=budget_config,
                    tenant_id=tenant_id,
                    session_id=session_id,
                    correlation_id=correlation_id,
                    transport="websocket",
                    user_input=user_input,
                    identity=identity,
                    budget_recorder=budget_recorder,
                    audit_pipeline=audit_pipeline,
                )
                if ingress_decision.decision != PolicyAction.ALLOW:
                    await websocket.send_json(_ingress_error_event(ingress_decision, correlation_id))
                    continue
                if turn_rate_limiter is not None:
                    allowed, retry_after_seconds = turn_rate_limiter.allow(tenant_id)
                    if not allowed:
                        if audit_pipeline is not None:
                            await audit_pipeline.emit(
                                event_type="turn_rejected_rate_limit",
                                correlation_id=correlation_id,
                                tenant_id=tenant_id,
                                payload={
                                    "runtime_id": "websocket",
                                    "session_id": session_id,
                                    "retry_after_seconds": retry_after_seconds,
                                },
                            )
                        await websocket.send_json(
                            {
                                "event": "error",
                                "code": "TENANT_TURN_RATE_LIMIT_EXCEEDED",
                                "message": "Too many turn requests in the current window.",
                                "retry_after_seconds": retry_after_seconds,
                            }
                        )
                        continue
                max_active_runs = max(int(websocket_settings.limits.max_active_runs_per_tenant), 0)
                if max_active_runs > 0 and run_registry.count_active_runs(tenant_id=tenant_id) >= max_active_runs:
                    if audit_pipeline is not None:
                        await audit_pipeline.emit(
                            event_type="turn_rejected_concurrency_limit",
                            correlation_id=correlation_id,
                            tenant_id=tenant_id,
                            payload={"runtime_id": "websocket", "session_id": session_id},
                        )
                    await websocket.send_json(
                        {
                            "event": "error",
                            "code": "TENANT_CONCURRENCY_LIMIT_EXCEEDED",
                            "message": "Too many active runs for this tenant.",
                        }
                    )
                    continue
                run_registry.start_run(
                    tenant_id=tenant_id,
                    session_id=session_id,
                    run_id=run_id,
                    correlation_id=correlation_id,
                    transport="websocket",
                )
                task = asyncio.create_task(
                    run_turn_task(
                        run_id=run_id,
                        user_input=user_input,
                        correlation_id=correlation_id,
                        ingress_decision=ingress_decision,
                    )
                )
                active_tasks[run_id] = task

            elif msg_type == "cancel":
                run_id = str(msg.get("run_id", ""))
                task = active_tasks.get(run_id)
                run_registry.request_cancel(
                    tenant_id=tenant_id,
                    run_id=run_id,
                    reason="websocket_cancel_message",
                )
                call_id_to_tool_name = dict(active_run_tool_calls.get(run_id, {}))
                _forward_runtime_cancellations(
                    execution_adapter=execution_adapter,
                    call_ids=set(call_id_to_tool_name.keys()),
                    terminal_event_seen=False,
                )
                if task and not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                active_tasks.pop(run_id, None)
                active_run_tool_calls.pop(run_id, None)
                for cancellation_event in _build_cancelled_progress_events(
                    call_id_to_tool_name=call_id_to_tool_name,
                    correlation_id=run_id,
                ):
                    await websocket.send_json(cancellation_event)
                _mark_cancelled_if_running(
                    run_registry,
                    tenant_id=tenant_id,
                    run_id=run_id,
                    terminal_event="websocket_cancel_message",
                )
                await websocket.send_json({"event": "run_cancelled", "run_id": run_id})

            else:
                await websocket.send_json(
                    {"event": "error", "code": "UNKNOWN_MESSAGE_TYPE",
                     "message": f"Unknown message type: '{msg_type}'"}
                )

    except WebSocketDisconnect:
        pass
    finally:
        # Cancel any in-flight tasks on disconnect
        for run_id, task in list(active_tasks.items()):
            if not task.done():
                task.cancel()
                run_registry.request_cancel(
                    tenant_id=tenant_id,
                    run_id=run_id,
                    reason="websocket_disconnect",
                )
                _forward_runtime_cancellations(
                    execution_adapter=execution_adapter,
                    call_ids=set(active_run_tool_calls.pop(run_id, {}).keys()),
                    terminal_event_seen=False,
                )
                _mark_cancelled_if_running(
                    run_registry,
                    tenant_id=tenant_id,
                    run_id=run_id,
                    terminal_event="websocket_disconnect",
                )
