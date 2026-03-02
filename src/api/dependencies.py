"""
File: dependencies.py
Path: src/api/dependencies.py
Role: FastAPI Depends() providers for tenant context, identity, policy overlay, and persistence stores.
Used By:
 - src/api/routers/tools.py
 - src/api/routers/agents.py
 - src/api/routers/sessions.py
 - src/api/routers/turns.py
 - src/api/routers/tenants.py
Depends On:
 - src/api/middleware/auth.py
 - src/runtime/tenant_runtime.py
 - src/tenancy/policy_overlay.py
 - src/persistence/contracts.py
Notes:
 - All dependencies raise HTTP 401/404 with clear messages — never silently swallow errors.
 - tenant_id comes from the path parameter; identity comes from the X-Identity header.
 - get_tool_store / get_agent_store return None when persistence_backend="memory" (tests).
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request

from src.api.middleware.auth import extract_identity, is_identity_usable
from src.identity.contracts import IdentityContext
from src.persistence.contracts import AgentStore, ToolStore
from src.runtime.tenant_runtime import TenantRuntimeContext, TenantRuntimeFactory
from src.tenancy.policy_overlay import TenantPolicyOverlayStore


def _get_tenant_factory(request: Request) -> TenantRuntimeFactory:
    return request.app.state.tenant_factory


def _get_policy_overlay_store(request: Request) -> TenantPolicyOverlayStore:
    return request.app.state.policy_overlay_store


async def get_identity(request: Request) -> IdentityContext:
    """Extract IdentityContext from the X-Identity header.

    Raises 401 if the header is missing or cannot be parsed.
    """
    identity = extract_identity(request)
    if identity is None:
        raise HTTPException(
            status_code=401,
            detail="Missing or malformed X-Identity header. "
            'Expected JSON: {"subject": "...", "roles": [...], "tenant_id": "..."}',
        )
    return identity


async def require_valid_identity(
    identity: IdentityContext = Depends(get_identity),
) -> IdentityContext:
    """Gate that rejects INVALID and EXPIRED token states.

    Returns the same IdentityContext if usable. Raises 401 otherwise.
    """
    if not is_identity_usable(identity):
        raise HTTPException(
            status_code=401,
            detail=f"Identity rejected: token_validation_state={identity.token_validation_state.value}",
        )
    return identity


async def get_tenant_context(
    tenant_id: str,
    factory: TenantRuntimeFactory = Depends(_get_tenant_factory),
) -> TenantRuntimeContext:
    """Return (or lazily create) the isolated TenantRuntimeContext for tenant_id.

    Never raises — get_or_create always returns a valid context.
    """
    return factory.get_or_create(tenant_id)


async def get_policy_overlay_store(
    store: TenantPolicyOverlayStore = Depends(_get_policy_overlay_store),
) -> TenantPolicyOverlayStore:
    return store


def get_tool_store(request: Request) -> ToolStore | None:
    """Return the ToolStore from app.state, or None when running in-memory (tests)."""
    return getattr(request.app.state, "tool_store", None)


def get_agent_store(request: Request) -> AgentStore | None:
    """Return the AgentStore from app.state, or None when running in-memory (tests)."""
    return getattr(request.app.state, "agent_store", None)
