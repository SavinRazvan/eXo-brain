"""
File: agents.py
Path: src/api/routers/agents.py
Role: Agent management endpoints — register, list, get, unregister agents, and manage handoff routes.
Used By:
 - src/api/app.py
Depends On:
 - src/api/dependencies.py
 - src/api/schemas/agent_schemas.py
 - src/runtime/tenant_runtime.py
 - src/agents/registry.py
 - src/agents/contracts.py
 - src/persistence/contracts.py
Notes:
 - All agents are stored in the tenant-scoped AgentRegistry — one per tenant, fully isolated.
 - HandoffRoute and HandoffFallbackPolicy changes take effect immediately on next routing decision.
 - Write-through to AgentStore on register/unregister (no-op when store is None, e.g. in tests).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request

from src.agents.contracts import (
    AgentCapabilityTag,
    AgentSpec,
    HandoffFallbackPolicy,
    HandoffRoute,
)
from src.api.dependencies import get_agent_store, get_tenant_context, require_valid_identity
from src.api.middleware.entitlements import (
    EntitlementDecision,
    emit_entitlement_decision_event,
    evaluate_feature_entitlement,
)
from src.api.schemas.agent_schemas import (
    AgentListResponse,
    AgentRegisterRequest,
    AgentResponse,
    HandoffFallbackPolicyRequest,
    HandoffFallbackPolicyResponse,
    HandoffRouteRequest,
    HandoffRouteResponse,
)
from src.identity.contracts import IdentityContext
from src.persistence.contracts import AgentStore, PersistedAgentRecord
from src.policies.entitlements import EntitledFeature
from src.runtime.tenant_runtime import TenantRuntimeContext
from src.schemas.tool_io import PolicyAction

router = APIRouter(tags=["agents"])


def _spec_to_response(spec: AgentSpec) -> AgentResponse:
    return AgentResponse(
        agent_id=spec.agent_id,
        role=spec.role,
        capability_tags=[tag.value for tag in spec.capability_tags],
        instructions=spec.instructions,
        metadata=spec.metadata,
    )


def _parse_capability_tags(tag_values: list[str]) -> set[AgentCapabilityTag]:
    """Convert string values to AgentCapabilityTag enum members; ignore unknown values."""
    valid = {t.value for t in AgentCapabilityTag}
    return {AgentCapabilityTag(v) for v in tag_values if v in valid}


def _entitlement_http_exception(decision: EntitlementDecision) -> HTTPException:
    return HTTPException(
        status_code=403,
        detail=f"{decision.reason_code}: {decision.message}",
    )


def _request_route_label(request: Request) -> str:
    route = request.scope.get("route")
    route_path = getattr(route, "path", request.url.path)
    return f"{request.method.upper()} {route_path}"


async def _require_agent_routing_entitlement(
    request: Request,
    tenant_id: str,
    identity: IdentityContext = Depends(require_valid_identity),
) -> IdentityContext:
    decision = evaluate_feature_entitlement(
        identity=identity,
        feature=EntitledFeature.GOVERNANCE_AGENT_ROUTING_ADVANCED,
    )
    correlation_id = f"entitlement_{uuid.uuid4().hex[:8]}"
    await emit_entitlement_decision_event(
        audit_pipeline=getattr(request.app.state, "tool_audit_pipeline", None),
        correlation_id=correlation_id,
        tenant_id=tenant_id,
        surface="agent_routing_controls",
        route=_request_route_label(request),
        decision=decision,
    )
    if decision.decision != PolicyAction.ALLOW:
        raise _entitlement_http_exception(decision)
    return identity


@router.post("/{tenant_id}/agents", status_code=201, response_model=AgentResponse)
async def register_agent(
    tenant_id: str,
    body: AgentRegisterRequest,
    ctx: TenantRuntimeContext = Depends(get_tenant_context),
    _identity: IdentityContext = Depends(require_valid_identity),
    agent_store: AgentStore | None = Depends(get_agent_store),
) -> AgentResponse:
    """Register a new agent in the tenant's agent registry."""
    spec = AgentSpec(
        agent_id=body.agent_id,
        role=body.role,
        capability_tags=_parse_capability_tags(body.capability_tags),
        instructions=body.instructions,
        metadata=body.metadata,
    )
    try:
        ctx.agent_registry.register(spec)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if agent_store is not None:
        record = PersistedAgentRecord(
            agent_id=spec.agent_id,
            role=spec.role,
            tenant_id=tenant_id,
            capability_tags=[tag.value for tag in spec.capability_tags],
            instructions=spec.instructions,
            metadata=spec.metadata,
        )
        await agent_store.save_agent(tenant_id, record)

    return _spec_to_response(spec)


@router.get("/{tenant_id}/agents", response_model=AgentListResponse)
async def list_agents(
    tenant_id: str,
    ctx: TenantRuntimeContext = Depends(get_tenant_context),
    _identity: IdentityContext = Depends(require_valid_identity),
) -> AgentListResponse:
    """List all agents registered in the tenant's registry."""
    agents = ctx.agent_registry.list_agents()
    return AgentListResponse(
        agents=[_spec_to_response(a) for a in agents],
        total=len(agents),
    )


# ---------------------------------------------------------------------------
# Handoff routes — defined BEFORE /{agent_id} to avoid path-param collision
# ---------------------------------------------------------------------------


@router.post("/{tenant_id}/agents/routes", status_code=201, response_model=HandoffRouteResponse)
async def add_handoff_route(
    tenant_id: str,
    body: HandoffRouteRequest,
    ctx: TenantRuntimeContext = Depends(get_tenant_context),
    _identity: IdentityContext = Depends(_require_agent_routing_entitlement),
) -> HandoffRouteResponse:
    """Add a handoff route between two registered agent roles."""
    required_caps = _parse_capability_tags(body.required_target_capabilities)
    route = HandoffRoute(
        source_role=body.source_role,
        target_role=body.target_role,
        reason=body.reason,
        required_target_capabilities=required_caps,
    )
    try:
        ctx.agent_registry.add_handoff_route(route)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return HandoffRouteResponse(
        source_role=route.source_role,
        target_role=route.target_role,
        reason=route.reason,
        required_target_capabilities=[c.value for c in route.required_target_capabilities],
    )


@router.get("/{tenant_id}/agents/routes", response_model=list[HandoffRouteResponse])
async def list_handoff_routes(
    tenant_id: str,
    ctx: TenantRuntimeContext = Depends(get_tenant_context),
    _identity: IdentityContext = Depends(_require_agent_routing_entitlement),
) -> list[HandoffRouteResponse]:
    """List all handoff routes for this tenant."""
    return [
        HandoffRouteResponse(
            source_role=r.source_role,
            target_role=r.target_role,
            reason=r.reason,
            required_target_capabilities=[c.value for c in r.required_target_capabilities],
        )
        for r in ctx.agent_registry.list_routes()
    ]


# ---------------------------------------------------------------------------
# Handoff fallback policies — defined BEFORE /{agent_id} to avoid collision
# ---------------------------------------------------------------------------


@router.post(
    "/{tenant_id}/agents/fallback",
    status_code=201,
    response_model=HandoffFallbackPolicyResponse,
)
async def set_fallback_policy(
    tenant_id: str,
    body: HandoffFallbackPolicyRequest,
    ctx: TenantRuntimeContext = Depends(get_tenant_context),
    _identity: IdentityContext = Depends(_require_agent_routing_entitlement),
) -> HandoffFallbackPolicyResponse:
    """Set a handoff fallback policy for a source role."""
    policy = HandoffFallbackPolicy(
        source_role=body.source_role,
        target_role=body.target_role,
        fallback_target_roles=body.fallback_target_roles,
        target_role_priorities=body.target_role_priorities,
    )
    try:
        ctx.agent_registry.set_handoff_fallback_policy(policy)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return HandoffFallbackPolicyResponse(
        source_role=policy.source_role,
        target_role=policy.target_role,
        fallback_target_roles=policy.fallback_target_roles,
        target_role_priorities=policy.target_role_priorities,
    )


@router.get("/{tenant_id}/agents/fallback", response_model=list[HandoffFallbackPolicyResponse])
async def list_fallback_policies(
    tenant_id: str,
    ctx: TenantRuntimeContext = Depends(get_tenant_context),
    _identity: IdentityContext = Depends(_require_agent_routing_entitlement),
) -> list[HandoffFallbackPolicyResponse]:
    """List all handoff fallback policies for this tenant."""
    return [
        HandoffFallbackPolicyResponse(
            source_role=p.source_role,
            target_role=p.target_role,
            fallback_target_roles=p.fallback_target_roles,
            target_role_priorities=p.target_role_priorities,
        )
        for p in ctx.agent_registry.list_fallback_policies()
    ]


# ---------------------------------------------------------------------------
# Single agent endpoints — AFTER fixed paths to avoid collision
# ---------------------------------------------------------------------------


@router.get("/{tenant_id}/agents/{agent_id}", response_model=AgentResponse)
async def get_agent(
    tenant_id: str,
    agent_id: str,
    ctx: TenantRuntimeContext = Depends(get_tenant_context),
    _identity: IdentityContext = Depends(require_valid_identity),
) -> AgentResponse:
    """Get full spec for a single agent."""
    try:
        spec = ctx.agent_registry.get(agent_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    return _spec_to_response(spec)


@router.delete("/{tenant_id}/agents/{agent_id}", status_code=204)
async def unregister_agent(
    tenant_id: str,
    agent_id: str,
    ctx: TenantRuntimeContext = Depends(get_tenant_context),
    _identity: IdentityContext = Depends(require_valid_identity),
    agent_store: AgentStore | None = Depends(get_agent_store),
) -> None:
    """Unregister an agent and cascade-clean its routes and fallback policies."""
    try:
        ctx.agent_registry.unregister(agent_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    if agent_store is not None:
        await agent_store.delete_agent(tenant_id, agent_id)
