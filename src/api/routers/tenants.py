"""
File: tenants.py
Path: src/api/routers/tenants.py
Role: Tenant policy overlay and quota management API endpoints.
Used By:
 - src/api/app.py
Depends On:
 - src/api/dependencies.py
 - src/api/schemas/tenant_schemas.py
 - src/runtime/tenant_runtime.py
 - src/tenancy/policy_overlay.py
Notes:
 - Policy overlay changes take effect immediately on the next tool call (no restart needed).
 - Quota limit changes take effect on the next check_submission call.
 - active_jobs in GET /quota returns 0 in MVP — BackgroundRuntime live tracking
   is a post-v1 addition (see deferred items in docs/plans/api-platform.md).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request

from src.api.dependencies import (
    get_app_modules,
    get_policy_overlay_store,
    get_tenant_context,
    require_valid_identity,
)
from src.api.middleware.entitlements import (
    EntitlementDecision,
    emit_entitlement_decision_event,
    evaluate_feature_entitlement,
    required_feature_for_governance_overlay,
)
from src.api.schemas.tenant_schemas import (
    PolicyOverlayRequest,
    PolicyOverlayResponse,
    PolicyTemplateApplyRequest,
    PolicyTemplateApplyResponse,
    PolicyTemplateListResponse,
    PolicyTemplateSummary,
    QuotaResponse,
    QuotaUpdateRequest,
)
from src.identity.contracts import IdentityContext
from src.policies.entitlements import EntitledFeature
from src.policies.ingress_profiles import resolve_ingress_profile_settings
from src.policies.policy_templates import (
    compile_policy_template_overlay,
    list_policy_templates as list_packaged_policy_templates,
    policy_template_summary_payload,
)
from src.policies.ingress_signed_plugins import classify_signed_plugin_lifecycle_transition
from src.runtime.tenant_runtime import TenantRuntimeContext
from src.schemas.tool_io import PolicyAction
from src.tenancy.policy_overlay import TenantPolicyOverlayStore

router = APIRouter(tags=["tenants"])


def _audit_pipeline(request: Request):
    modules = get_app_modules(request)
    if modules is None:
        return None
    return modules.audit_observability.tool_audit_pipeline


def _run_registry(request: Request):
    modules = get_app_modules(request)
    if modules is None:
        return None
    return modules.session_runtime.run_control_registry


def _policy_entitlement_http_exception(decision: EntitlementDecision) -> HTTPException:
    return HTTPException(
        status_code=403,
        detail=f"{decision.reason_code}: {decision.message}",
    )


def _policy_validation_http_exception(message: str) -> HTTPException:
    return HTTPException(
        status_code=422,
        detail=message,
    )


def _policy_conflict_http_exception(message: str) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail=message,
    )


def _active_run_count(request: Request, tenant_id: str) -> int:
    run_registry = _run_registry(request)
    if run_registry is None:
        return 0
    return int(run_registry.count_active_runs(tenant_id=tenant_id))


async def _emit_ingress_profile_audit_events(
    *,
    request: Request,
    tenant_id: str,
    correlation_id: str,
    surface: str,
    route: str,
    ingress_audit_payload: dict,
    lifecycle_action: str,
    previous_plugin_ref: str,
    new_plugin_ref: str,
    active_run_count: int,
) -> None:
    audit_pipeline = _audit_pipeline(request)
    if audit_pipeline is None:
        return
    await audit_pipeline.emit(
        event_type="tenant_policy_ingress_profile_configured",
        correlation_id=correlation_id,
        tenant_id=tenant_id,
        payload={
            "surface": surface,
            "route": route,
            **ingress_audit_payload,
        },
    )
    if lifecycle_action == "none":
        return
    await audit_pipeline.emit(
        event_type="tenant_policy_signed_gate_plugin_lifecycle",
        correlation_id=correlation_id,
        tenant_id=tenant_id,
        payload={
            "surface": surface,
            "route": route,
            "action": lifecycle_action,
            "previous_signed_gate_plugin_ref": previous_plugin_ref,
            "new_signed_gate_plugin_ref": new_plugin_ref,
            "active_run_count": active_run_count,
            **ingress_audit_payload,
        },
    )


# ─── Policy overlay ───────────────────────────────────────────────────────────


@router.get(
    "/{tenant_id}/policy",
    response_model=PolicyOverlayResponse,
    summary="Get tenant policy overlay",
)
async def get_policy(
    tenant_id: str,
    store: TenantPolicyOverlayStore = Depends(get_policy_overlay_store),
    _identity: IdentityContext = Depends(require_valid_identity),
) -> PolicyOverlayResponse:
    """Return the current active policy overlay for the tenant.

    Returns an empty overlay dict if none has been set yet.
    """
    overlay = store.get_overlay(tenant_id)
    return PolicyOverlayResponse(tenant_id=tenant_id, overlay=overlay)


@router.get(
    "/{tenant_id}/policy/templates",
    response_model=PolicyTemplateListResponse,
    summary="List packaged policy templates",
)
async def list_policy_templates(
    tenant_id: str,
    request: Request,
    _store: TenantPolicyOverlayStore = Depends(get_policy_overlay_store),
    identity: IdentityContext = Depends(require_valid_identity),
) -> PolicyTemplateListResponse:
    """Return packaged policy templates available for tenant governance controls."""
    correlation_id = f"entitlement_{uuid.uuid4().hex[:8]}"
    entitlement_decision = evaluate_feature_entitlement(
        identity=identity,
        feature=EntitledFeature.GOVERNANCE_POLICY_TEMPLATES,
    )
    await emit_entitlement_decision_event(
        audit_pipeline=_audit_pipeline(request),
        correlation_id=correlation_id,
        tenant_id=tenant_id,
        surface="tenant_policy_template_catalog",
        route="GET /tenants/{tenant_id}/policy/templates",
        decision=entitlement_decision,
    )
    if entitlement_decision.decision != PolicyAction.ALLOW:
        raise _policy_entitlement_http_exception(entitlement_decision)
    templates = [
        PolicyTemplateSummary(**policy_template_summary_payload(template))
        for template in list_packaged_policy_templates()
    ]
    return PolicyTemplateListResponse(tenant_id=tenant_id, templates=templates)


@router.post(
    "/{tenant_id}/policy/templates/{template_id:path}/apply",
    response_model=PolicyTemplateApplyResponse,
    summary="Apply packaged policy template",
)
async def apply_policy_template(
    tenant_id: str,
    template_id: str,
    body: PolicyTemplateApplyRequest,
    request: Request,
    store: TenantPolicyOverlayStore = Depends(get_policy_overlay_store),
    identity: IdentityContext = Depends(require_valid_identity),
) -> PolicyTemplateApplyResponse:
    """Apply a packaged policy template and persist resulting tenant overlay."""
    previous_overlay = dict(store.get_overlay(tenant_id))
    try:
        template, overlay, ingress_resolution = compile_policy_template_overlay(
            template_id=template_id,
            merge_with_overlay=previous_overlay if body.merge_with_existing else None,
            overlay_extra=body.extra,
        )
    except ValueError as exc:
        raise _policy_validation_http_exception(str(exc)) from exc

    correlation_id = f"entitlement_{uuid.uuid4().hex[:8]}"
    route = "POST /tenants/{tenant_id}/policy/templates/{template_id}/apply"
    audit_pipeline = _audit_pipeline(request)

    template_access_decision = evaluate_feature_entitlement(
        identity=identity,
        feature=EntitledFeature.GOVERNANCE_POLICY_TEMPLATES,
    )
    await emit_entitlement_decision_event(
        audit_pipeline=audit_pipeline,
        correlation_id=correlation_id,
        tenant_id=tenant_id,
        surface="tenant_policy_template_apply",
        route=route,
        decision=template_access_decision,
        extra_payload={
            "template_id": template.template_id,
            "packaged_risk_profile_id": template.packaged_risk_profile_id,
            "merge_with_existing": body.merge_with_existing,
        },
    )
    if template_access_decision.decision != PolicyAction.ALLOW:
        raise _policy_entitlement_http_exception(template_access_decision)

    overlay_feature = required_feature_for_governance_overlay(overlay)
    overlay_entitlement_decision = evaluate_feature_entitlement(
        identity=identity,
        feature=overlay_feature,
    )
    await emit_entitlement_decision_event(
        audit_pipeline=audit_pipeline,
        correlation_id=correlation_id,
        tenant_id=tenant_id,
        surface="tenant_policy_template_apply_overlay",
        route=route,
        decision=overlay_entitlement_decision,
        extra_payload={
            "template_id": template.template_id,
            "packaged_risk_profile_id": template.packaged_risk_profile_id,
            "merge_with_existing": body.merge_with_existing,
        },
    )
    if overlay_entitlement_decision.decision != PolicyAction.ALLOW:
        raise _policy_entitlement_http_exception(overlay_entitlement_decision)

    previous_plugin_ref = str(previous_overlay.get("signed_gate_plugin_ref", "")).strip()
    next_plugin_ref = str(overlay.get("signed_gate_plugin_ref", "")).strip()
    active_run_count = _active_run_count(request, tenant_id)
    try:
        lifecycle = classify_signed_plugin_lifecycle_transition(
            previous_plugin_ref=previous_plugin_ref,
            new_plugin_ref=next_plugin_ref,
            active_run_count=active_run_count,
        )
    except ValueError as exc:
        raise _policy_conflict_http_exception(str(exc)) from exc

    store.set_overlay(tenant_id, overlay)
    ingress_audit_payload = ingress_resolution.to_audit_payload()
    await _emit_ingress_profile_audit_events(
        request=request,
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        surface="tenant_policy_template_apply",
        route=route,
        ingress_audit_payload=ingress_audit_payload,
        lifecycle_action=lifecycle.action,
        previous_plugin_ref=lifecycle.previous_plugin_ref,
        new_plugin_ref=lifecycle.new_plugin_ref,
        active_run_count=active_run_count,
    )
    if audit_pipeline is not None:
        await audit_pipeline.emit(
            event_type="tenant_policy_template_applied",
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            payload={
                "surface": "tenant_policy_template_apply",
                "route": route,
                "template_id": template.template_id,
                "packaged_risk_profile_id": template.packaged_risk_profile_id,
                "minimum_tier": template.minimum_tier,
                "merge_with_existing": body.merge_with_existing,
                "extra_keys": sorted(body.extra.keys()),
                **ingress_audit_payload,
            },
        )
    return PolicyTemplateApplyResponse(
        tenant_id=tenant_id,
        template_id=template.template_id,
        packaged_risk_profile_id=template.packaged_risk_profile_id,
        overlay=overlay,
    )


@router.put(
    "/{tenant_id}/policy",
    response_model=PolicyOverlayResponse,
    summary="Set tenant policy overlay",
)
async def set_policy(
    tenant_id: str,
    body: PolicyOverlayRequest,
    request: Request,
    store: TenantPolicyOverlayStore = Depends(get_policy_overlay_store),
    identity: IdentityContext = Depends(require_valid_identity),
) -> PolicyOverlayResponse:
    """Apply a policy overlay for the tenant.

    Changes take effect immediately — no restart needed.
    The overlay is merged into the payload dict stored by TenantPolicyOverlayStore
    and consulted by DeterministicFirstPolicyMiddleware on every tool call.
    """
    previous_overlay = dict(store.get_overlay(tenant_id))
    overlay: dict = {
        "deny_tools": body.deny_tools,
        "escalate_risk_tiers": body.escalate_risk_tiers,
        "escalate_state_changing": body.escalate_state_changing,
        **body.extra,
    }
    try:
        ingress_resolution = resolve_ingress_profile_settings(overlay)
    except ValueError as exc:
        raise _policy_validation_http_exception(str(exc)) from exc
    normalized_ingress_patch = ingress_resolution.to_overlay_patch()
    feature = required_feature_for_governance_overlay(overlay)
    entitlement_decision = evaluate_feature_entitlement(identity=identity, feature=feature)
    correlation_id = f"entitlement_{uuid.uuid4().hex[:8]}"
    await emit_entitlement_decision_event(
        audit_pipeline=_audit_pipeline(request),
        correlation_id=correlation_id,
        tenant_id=tenant_id,
        surface="tenant_policy_overlay",
        route="PUT /tenants/{tenant_id}/policy",
        decision=entitlement_decision,
    )
    if entitlement_decision.decision != PolicyAction.ALLOW:
        raise _policy_entitlement_http_exception(entitlement_decision)

    previous_plugin_ref = str(previous_overlay.get("signed_gate_plugin_ref", "")).strip()
    next_plugin_ref = str(normalized_ingress_patch.get("signed_gate_plugin_ref", "")).strip()
    run_registry = _run_registry(request)
    active_run_count = 0
    if run_registry is not None:
        active_run_count = int(run_registry.count_active_runs(tenant_id=tenant_id))
    try:
        lifecycle = classify_signed_plugin_lifecycle_transition(
            previous_plugin_ref=previous_plugin_ref,
            new_plugin_ref=next_plugin_ref,
            active_run_count=active_run_count,
        )
    except ValueError as exc:
        raise _policy_conflict_http_exception(str(exc)) from exc

    overlay.update(normalized_ingress_patch)
    store.set_overlay(tenant_id, overlay)
    audit_pipeline = _audit_pipeline(request)
    if audit_pipeline is not None:
        await audit_pipeline.emit(
            event_type="tenant_policy_ingress_profile_configured",
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            payload={
                "surface": "tenant_policy_overlay",
                "route": "PUT /tenants/{tenant_id}/policy",
                **ingress_resolution.to_audit_payload(),
            },
        )
        if lifecycle.action != "none":
            await audit_pipeline.emit(
                event_type="tenant_policy_signed_gate_plugin_lifecycle",
                correlation_id=correlation_id,
                tenant_id=tenant_id,
                payload={
                    "surface": "tenant_policy_overlay",
                    "route": "PUT /tenants/{tenant_id}/policy",
                    "action": lifecycle.action,
                    "previous_signed_gate_plugin_ref": lifecycle.previous_plugin_ref,
                    "new_signed_gate_plugin_ref": lifecycle.new_plugin_ref,
                    "active_run_count": active_run_count,
                    **ingress_resolution.to_audit_payload(),
                },
            )
    return PolicyOverlayResponse(tenant_id=tenant_id, overlay=overlay)


# ─── Quota management ─────────────────────────────────────────────────────────


@router.get(
    "/{tenant_id}/quota",
    response_model=QuotaResponse,
    summary="Get tenant quota",
)
async def get_quota(
    tenant_id: str,
    ctx: TenantRuntimeContext = Depends(get_tenant_context),
    _identity: IdentityContext = Depends(require_valid_identity),
) -> QuotaResponse:
    """Return the current quota configuration for the tenant.

    `active_jobs` is 0 in MVP — live BackgroundRuntime tracking is post-v1.
    """
    return QuotaResponse(
        tenant_id=tenant_id,
        max_active_jobs=ctx.quota_manager.max_active_jobs,
        active_jobs=0,
    )


@router.put(
    "/{tenant_id}/quota",
    response_model=QuotaResponse,
    summary="Update tenant quota",
)
async def update_quota(
    tenant_id: str,
    body: QuotaUpdateRequest,
    ctx: TenantRuntimeContext = Depends(get_tenant_context),
    _identity: IdentityContext = Depends(require_valid_identity),
) -> QuotaResponse:
    """Update the concurrent background job limit for the tenant.

    Setting max_active_jobs=0 means unlimited.
    Changes take effect on the next check_submission call.
    """
    try:
        ctx.quota_manager.set_limit(body.max_active_jobs)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return QuotaResponse(
        tenant_id=tenant_id,
        max_active_jobs=ctx.quota_manager.max_active_jobs,
        active_jobs=0,
    )
