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
 - Prefer `AppModules` from `app.state.modules` when present; raw `app.state.*` fallbacks remain for
   narrow test doubles that omit the module container.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request

from src.api.middleware.auth import extract_identity, is_identity_usable
from src.identity.contracts import IdentityContext
from src.modules.platform_bootstrap.service import AppModules, app_modules_from_requestlike
from src.persistence.contracts import AgentStore, ToolStore, ToolVersionStore
from src.runtime.tenant_runtime import TenantRuntimeContext, TenantRuntimeFactory
from src.tenancy.policy_overlay import TenantPolicyOverlayStore


def get_app_modules(request: Request) -> AppModules | None:
    return app_modules_from_requestlike(request)


def _get_tenant_factory(request: Request) -> TenantRuntimeFactory:
    modules = get_app_modules(request)
    if modules is not None:
        return modules.session_runtime.tenant_factory
    return request.app.state.tenant_factory


def _get_policy_overlay_store(request: Request) -> TenantPolicyOverlayStore:
    modules = get_app_modules(request)
    if modules is not None:
        return modules.tenant_governance.policy_overlay_store
    return request.app.state.policy_overlay_store


async def get_identity(request: Request) -> IdentityContext:
    """Resolve IdentityContext from the request.

    Tries Authorization: Bearer (JWT or API-key), X-API-Key, then X-Identity (test/dev only).
    Raises 401 if no valid identity can be resolved.
    """
    identity = await extract_identity(request)
    if identity is None:
        raise HTTPException(
            status_code=401,
            detail=(
                "Authentication required. Provide 'Authorization: Bearer <token>', "
                "'X-API-Key: <key>', or (test/dev only) 'X-Identity: <json>'."
            ),
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


def _cross_tenant_admin_allowed(request: Request, identity: IdentityContext) -> bool:
    """Return True if explicit cross-tenant admin bypass is enabled and role matches.

    Bypass is intentionally restricted to tenant-scoped admin routes only.
    """
    path = str(getattr(request.url, "path", "")).strip()
    if "/tenants/" not in path or "/admin/" not in path:
        return False
    modules = get_app_modules(request)
    if modules is not None:
        return modules.identity_access.service.allow_cross_tenant_admin_access(identity)
    settings = getattr(request.app.state, "settings", None)
    auth = getattr(settings, "auth", None)
    allow_bypass = bool(getattr(auth, "allow_cross_tenant_admin", False))
    if not allow_bypass:
        return False
    configured_roles = getattr(auth, "cross_tenant_admin_roles", ["super_admin"])
    allowed_roles = {str(role).strip() for role in configured_roles if str(role).strip()}
    if not allowed_roles:
        return False
    return any(role in allowed_roles for role in identity.roles)


def enforce_tenant_scope(
    *,
    tenant_id: str,
    identity: IdentityContext,
    request: Request,
) -> None:
    """Enforce tenant-scoped route isolation (with optional explicit admin bypass)."""
    identity_tenant = str(identity.tenant_id or "").strip()
    path_tenant = str(tenant_id or "").strip()
    if identity_tenant and identity_tenant == path_tenant:
        return
    if _cross_tenant_admin_allowed(request, identity):
        return
    raise HTTPException(
        status_code=403,
        detail=(
            "TENANT_SCOPE_MISMATCH: authenticated identity is not allowed to access "
            f"tenant '{path_tenant}'."
        ),
    )


async def require_tenant_scope_identity(
    tenant_id: str,
    request: Request,
    identity: IdentityContext = Depends(require_valid_identity),
) -> IdentityContext:
    """Require valid identity and enforce identity tenant against path tenant."""
    enforce_tenant_scope(tenant_id=tenant_id, identity=identity, request=request)
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
    modules = get_app_modules(request)
    if modules is not None:
        return modules.tool_management.tool_store
    return getattr(request.app.state, "tool_store", None)


def get_agent_store(request: Request) -> AgentStore | None:
    """Return the AgentStore from app.state, or None when running in-memory (tests)."""
    modules = get_app_modules(request)
    if modules is not None:
        return modules.agent_management.agent_store
    return getattr(request.app.state, "agent_store", None)


def get_tool_version_store(request: Request) -> ToolVersionStore | None:
    """Return the ToolVersionStore from app.state, or None when running in-memory (tests)."""
    modules = get_app_modules(request)
    if modules is not None:
        return modules.tool_management.tool_version_store
    return getattr(request.app.state, "tool_version_store", None)


def get_run_control_registry(request: Request):
    """Return the app-scoped run control registry."""
    modules = get_app_modules(request)
    if modules is not None:
        return modules.session_runtime.run_control_registry
    return getattr(request.app.state, "run_control_registry", None)
