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

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request

from src.api.dependencies import get_tenant_context, require_valid_identity
from src.api.schemas.session_schemas import (
    SessionCreateRequest,
    SessionCreateResponse,
    SessionStateResponse,
)
from src.core.session_context import SessionContext
from src.identity.contracts import IdentityContext
from src.persistence.contracts import SessionRecord
from src.runtime.tenant_runtime import TenantRuntimeContext

router = APIRouter(tags=["sessions"])


def _get_factory(request: Request):
    return request.app.state.tenant_factory


@router.post("/{tenant_id}/sessions", status_code=201, response_model=SessionCreateResponse)
async def create_session(
    tenant_id: str,
    body: SessionCreateRequest,
    request: Request,
    ctx: TenantRuntimeContext = Depends(get_tenant_context),
    identity: IdentityContext = Depends(require_valid_identity),
) -> SessionCreateResponse:
    """Create a new agent session for a tenant.

    Resolves agent spec and wires provider adapter. Returns 404 if agent_id or
    provider_id is not registered. Returns 404 if provider adapter is missing.
    """
    session_id = f"sess_{uuid.uuid4().hex}"
    correlation_id = body.correlation_id or session_id
    factory = _get_factory(request)

    try:
        factory.create_session_runtime(
            tenant_context=ctx,
            agent_id=body.agent_id,
            provider_id=body.provider_id,
            session_id=session_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    session_ctx = SessionContext(
        session_id=session_id,
        run_id=f"run_{uuid.uuid4().hex[:8]}",
        job_id=f"job_{uuid.uuid4().hex[:8]}",
        task_id=f"task_{uuid.uuid4().hex[:8]}",
        agent_id=body.agent_id,
        provider_id=body.provider_id,
        correlation_id=correlation_id,
        identity=identity,
        metadata={
            "agent_id": body.agent_id,
            "provider_id": body.provider_id,
            "correlation_id": correlation_id,
        },
    )
    record = SessionRecord(
        session=session_ctx,
        tenant_id=tenant_id,
        state="active",
        data={
            "agent_id": body.agent_id,
            "provider_id": body.provider_id,
            "correlation_id": correlation_id,
        },
    )
    await ctx.session_store.save_session(record)

    return SessionCreateResponse(
        session_id=session_id,
        tenant_id=tenant_id,
        agent_id=body.agent_id,
        provider_id=body.provider_id,
        correlation_id=correlation_id,
    )


@router.get(
    "/{tenant_id}/sessions/{session_id}",
    response_model=SessionStateResponse,
)
async def get_session(
    tenant_id: str,
    session_id: str,
    ctx: TenantRuntimeContext = Depends(get_tenant_context),
    _identity: IdentityContext = Depends(require_valid_identity),
) -> SessionStateResponse:
    """Retrieve session state from the session store."""
    record = await ctx.session_store.get_session(session_id, tenant_id=tenant_id)
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
