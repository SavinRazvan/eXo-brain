"""
File: sessions.py
Path: src/api/routers/sessions.py
Role: Session lifecycle endpoints — create and retrieve sessions per tenant.
Used By:
 - src/api/app.py
Depends On:
 - src/api/dependencies.py
 - src/api/schemas/session_schemas.py
 - src/runtime/tenant_runtime.py
 - src/persistence/contracts.py
 - src/core/session_context.py
Notes:
 - Session creation wires a per-session Orchestrator + HostAdapter via TenantRuntimeFactory.
 - Session metadata (agent_id, provider_id, correlation_id) is stored in the SessionStore
   so the GET endpoint can reconstruct the state without querying the factory.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from src.api.dependencies import get_app_modules, require_valid_identity
from src.api.schemas.session_schemas import (
    SessionCreateRequest,
    SessionCreateResponse,
    SessionStateResponse,
)
from src.identity.contracts import IdentityContext
from src.modules.session_runtime.service import SessionRuntimeError

router = APIRouter(tags=["sessions"])


@router.post("/{tenant_id}/sessions", status_code=201, response_model=SessionCreateResponse)
async def create_session(
    tenant_id: str,
    body: SessionCreateRequest,
    request: Request,
    identity: IdentityContext = Depends(require_valid_identity),
) -> SessionCreateResponse:
    """Create a new agent session for a tenant.

    Resolves agent spec and wires provider adapter. Returns 404 if agent_id or
    provider_id is not registered. Returns 404 if provider adapter is missing.
    """
    modules = get_app_modules(request)
    service = modules.session_runtime.service if modules is not None else None
    if service is None:
        raise HTTPException(status_code=503, detail="Session runtime module is not configured.")
    try:
        session_ctx = await service.create_session(
            tenant_id=tenant_id,
            agent_id=body.agent_id,
            provider_id=body.provider_id,
            correlation_id=body.correlation_id,
            identity=identity,
        )
    except SessionRuntimeError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return SessionCreateResponse(
        session_id=session_ctx.session_id,
        tenant_id=tenant_id,
        agent_id=body.agent_id,
        provider_id=body.provider_id,
        correlation_id=session_ctx.correlation_id,
    )


@router.get(
    "/{tenant_id}/sessions/{session_id}",
    response_model=SessionStateResponse,
)
async def get_session(
    tenant_id: str,
    session_id: str,
    request: Request,
    _identity: IdentityContext = Depends(require_valid_identity),
) -> SessionStateResponse:
    """Retrieve session state from the session store."""
    modules = get_app_modules(request)
    service = modules.session_runtime.service if modules is not None else None
    if service is None:
        raise HTTPException(status_code=503, detail="Session runtime module is not configured.")
    try:
        record = await service.get_session(tenant_id=tenant_id, session_id=session_id)
    except SessionRuntimeError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    if record is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return SessionStateResponse(
        session_id=session_id,
        tenant_id=tenant_id,
        agent_id=record.data.get("agent_id", record.session.agent_id),
        provider_id=record.data.get("provider_id", record.session.provider_id),
        correlation_id=record.data.get("correlation_id", record.session.correlation_id),
        created_at="",
    )
