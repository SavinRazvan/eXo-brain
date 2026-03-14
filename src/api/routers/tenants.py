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
    get_policy_overlay_store,
    get_tenant_context,
    require_valid_identity,
)
from src.api.middleware.entitlements import (
    EntitlementDecision,
    evaluate_feature_entitlement,
    required_feature_for_governance_overlay,
)
from src.api.schemas.tenant_schemas import (
    PolicyOverlayRequest,
    PolicyOverlayResponse,
    QuotaResponse,
    QuotaUpdateRequest,
)
from src.identity.contracts import IdentityContext
from src.runtime.tenant_runtime import TenantRuntimeContext
from src.schemas.tool_io import PolicyAction
from src.tenancy.policy_overlay import TenantPolicyOverlayStore

router = APIRouter(tags=["tenants"])


def _policy_entitlement_http_exception(decision: EntitlementDecision) -> HTTPException:
    return HTTPException(
        status_code=403,
        detail=f"{decision.reason_code}: {decision.message}",
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
    feature = required_feature_for_governance_overlay(body.extra)
    entitlement_decision = evaluate_feature_entitlement(identity=identity, feature=feature)
    correlation_id = f"entitlement_{uuid.uuid4().hex[:8]}"
    audit_pipeline = getattr(request.app.state, "tool_audit_pipeline", None)
    if audit_pipeline is not None:
        await audit_pipeline.emit(
            event_type="entitlement_decision",
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            payload={
                "surface": "tenant_policy_overlay",
                "route": "PUT /tenants/{tenant_id}/policy",
                **entitlement_decision.to_payload(),
            },
        )
    if entitlement_decision.decision != PolicyAction.ALLOW:
        raise _policy_entitlement_http_exception(entitlement_decision)

    overlay: dict = {
        "deny_tools": body.deny_tools,
        "escalate_risk_tiers": body.escalate_risk_tiers,
        "escalate_state_changing": body.escalate_state_changing,
        **body.extra,
    }
    store.set_overlay(tenant_id, overlay)
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
