"""
File: providers.py
Path: src/api/routers/providers.py
Role: Provider listing, health, capabilities, and dynamic registration endpoints.
Used By:
 - src/api/app.py
Depends On:
 - src/api/dependencies.py
 - src/api/schemas/provider_schemas.py
 - src/config/provider_registry.py
 - src/runtime/adapter_factory.py
 - src/runtime/capability_map.py
Notes:
 - Provider endpoints are tenant-agnostic — providers are shared across all tenants.
 - Healthcheck calls the live adapter's healthcheck() coroutine; may take up to adapter timeout.
 - POST /providers requires healthcheck to pass before 201; DELETE returns 409 if active sessions exist.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from src.api.dependencies import get_app_modules, require_valid_identity
from src.api.schemas.provider_schemas import (
    ProviderCapabilitiesResponse,
    ProviderHealthResponse,
    ProviderListResponse,
    ProviderRegisterRequest,
    ProviderRegisterResponse,
    ProviderSummaryResponse,
)
from src.identity.contracts import IdentityContext
from src.modules.provider_management.service import ProviderManagementError

router = APIRouter(tags=["providers"])


def _get_provider_registry(request: Request):
    modules = get_app_modules(request)
    if modules is None:
        raise HTTPException(status_code=503, detail="Provider management module is not configured.")
    return modules.provider_management.registry


def _get_provider_service(request: Request):
    modules = get_app_modules(request)
    if modules is not None:
        return modules.provider_management.service
    return None


def _get_provider_store(request: Request):
    modules = get_app_modules(request)
    if modules is None:
        raise HTTPException(status_code=503, detail="Provider management module is not configured.")
    return modules.provider_management.store


def _get_session_store(request: Request):
    modules = get_app_modules(request)
    if modules is None:
        raise HTTPException(status_code=503, detail="Session runtime module is not configured.")
    return modules.session_runtime.session_store


def _can_use_provider_drain(request: Request, identity: IdentityContext) -> bool:
    modules = get_app_modules(request)
    if modules is None:
        raise HTTPException(status_code=503, detail="Application modules are not configured.")
    settings = modules.platform_bootstrap.settings
    runtime = getattr(settings, "runtime", None) if settings is not None else None
    drain_enabled = bool(getattr(runtime, "enable_provider_delete_graceful_drain", False))
    if not drain_enabled:
        return False
    return modules.identity_access.service.is_platform_admin(identity)


@router.post("/providers", status_code=201, response_model=ProviderRegisterResponse)
async def register_provider(
    body: ProviderRegisterRequest,
    request: Request,
    identity: IdentityContext = Depends(require_valid_identity),
) -> ProviderRegisterResponse:
    """Register a new provider dynamically.

    Loads the adapter via adapter_class_ref, runs healthcheck, then persists and registers.
    Returns 422 if the adapter cannot be loaded or healthcheck fails.
    """
    service = _get_provider_service(request)
    if service is None:
        raise HTTPException(status_code=503, detail="Provider management module is not configured.")
    try:
        record = await service.register_provider(
            identity=identity,
            provider_id=body.provider_id,
            display_name=body.display_name,
            adapter_class_ref=body.adapter_class_ref,
            api_key_env_var=body.api_key_env_var,
            base_url=body.base_url,
            model=body.model,
            profile=body.profile,
            api_type=body.api_type,
        )
    except ProviderManagementError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return ProviderRegisterResponse(
        provider_id=record.provider_id,
        display_name=record.display_name,
        enabled=record.enabled,
        profile=record.profile.value,
    )


@router.delete("/providers/{provider_id}", status_code=204)
async def unregister_provider(
    provider_id: str,
    request: Request,
    force_drain: bool = False,
    identity: IdentityContext = Depends(require_valid_identity),
) -> None:
    """Unregister a provider. Returns 409 if active sessions use this provider."""
    service = _get_provider_service(request)
    if service is None:
        raise HTTPException(status_code=503, detail="Provider management module is not configured.")
    session_store = _get_session_store(request)
    modules = get_app_modules(request)
    tenant_factory = modules.session_runtime.tenant_factory if modules is not None else None
    drain_enabled = _can_use_provider_drain(request, identity)
    try:
        await service.unregister_provider(
            identity=identity,
            provider_id=provider_id,
            session_store=session_store,
            tenant_factory=tenant_factory,
            force_drain=force_drain,
            drain_enabled=drain_enabled,
        )
    except ProviderManagementError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return None


@router.get("/providers", response_model=ProviderListResponse)
async def list_providers(
    request: Request,
    _identity: IdentityContext = Depends(require_valid_identity),
) -> ProviderListResponse:
    """List all registered provider IDs with their profile information."""
    registry = _get_provider_registry(request)
    providers: list[ProviderSummaryResponse] = []
    for provider_id in sorted(registry._providers.keys()):
        record = registry._providers[provider_id]
        providers.append(
            ProviderSummaryResponse(
                provider_id=record.provider_id,
                display_name=record.display_name,
                enabled=record.enabled,
                profile=record.profile.value,
                recommended_runtime_mode="hybrid",
            )
        )
    return ProviderListResponse(providers=providers, total=len(providers))


@router.get("/providers/{provider_id}/health", response_model=ProviderHealthResponse)
async def get_provider_health(
    provider_id: str,
    request: Request,
    _identity: IdentityContext = Depends(require_valid_identity),
) -> ProviderHealthResponse:
    """Call the adapter's healthcheck and return current health state."""
    registry = _get_provider_registry(request)
    try:
        adapter = registry.get_adapter(provider_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' not found")

    health = await adapter.healthcheck()
    return ProviderHealthResponse(
        provider_id=provider_id,
        state=health.state.value,
        reason=health.reason,
    )


@router.get("/providers/{provider_id}/capabilities", response_model=ProviderCapabilitiesResponse)
async def get_provider_capabilities(
    provider_id: str,
    request: Request,
    _identity: IdentityContext = Depends(require_valid_identity),
) -> ProviderCapabilitiesResponse:
    """Return the capability map for a registered provider adapter."""
    registry = _get_provider_registry(request)
    try:
        adapter = registry.get_adapter(provider_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' not found")

    caps = adapter.get_capabilities()
    return ProviderCapabilitiesResponse(
        provider_id=provider_id,
        supports_streaming=caps.supports_streaming,
        supports_function_calling=caps.supports_function_calling,
        supports_structured_output=caps.supports_structured_output,
        supports_handoffs=caps.supports_handoffs,
        supports_agents_sdk_native=caps.supports_agents_sdk_native,
        supports_openai_compatible_api=caps.supports_openai_compatible_api,
        reliability_score=caps.reliability_score,
        security_tier=caps.security_tier.value,
        recommended_runtime_mode=caps.recommended_runtime_mode,
        extras={},
    )
