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

from src.api.dependencies import require_valid_identity
from src.api.schemas.provider_schemas import (
    ProviderCapabilitiesResponse,
    ProviderHealthResponse,
    ProviderListResponse,
    ProviderRegisterRequest,
    ProviderRegisterResponse,
    ProviderSummaryResponse,
)
from src.config.provider_registry import (
    AuthConfig,
    EndpointApiType,
    EndpointConfig,
    ModelDefaults,
    ProviderProfile,
    ProviderRecord,
)
from src.identity.contracts import IdentityContext
from src.persistence.contracts import PersistedProviderRecord, ProviderStore
from src.runtime.adapter_factory import canonicalize_adapter_class_ref, load_adapter
from src.runtime.capability_map import HealthState

router = APIRouter(tags=["providers"])


def _get_provider_registry(request: Request):
    return request.app.state.provider_registry


def _get_provider_store(request: Request) -> ProviderStore | None:
    return getattr(request.app.state, "provider_store", None)


def _get_session_store(request: Request):
    return getattr(request.app.state, "session_store", None)


def _can_use_provider_drain(request: Request, identity: IdentityContext) -> bool:
    settings = getattr(request.app.state, "settings", None)
    runtime = getattr(settings, "runtime", None) if settings is not None else None
    drain_enabled = bool(getattr(runtime, "enable_provider_delete_graceful_drain", False))
    if not drain_enabled:
        return False
    roles = {str(role).strip() for role in identity.roles if str(role).strip()}
    return bool({"admin", "super_admin", "platform_admin"} & roles)


@router.post("/providers", status_code=201, response_model=ProviderRegisterResponse)
async def register_provider(
    body: ProviderRegisterRequest,
    request: Request,
    _identity: IdentityContext = Depends(require_valid_identity),
) -> ProviderRegisterResponse:
    """Register a new provider dynamically.

    Loads the adapter via adapter_class_ref, runs healthcheck, then persists and registers.
    Returns 422 if the adapter cannot be loaded or healthcheck fails.
    """
    store = _get_provider_store(request)
    if store is None:
        raise HTTPException(
            status_code=503,
            detail="Provider store is not configured (memory backend).",
        )
    registry = _get_provider_registry(request)
    if body.provider_id in registry._providers:
        raise HTTPException(
            status_code=409,
            detail=f"Provider '{body.provider_id}' is already registered.",
        )
    canonical_ref = canonicalize_adapter_class_ref(body.adapter_class_ref)
    try:
        adapter = load_adapter(canonical_ref, provider_id=body.provider_id)
    except (ValueError, ImportError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    health = await adapter.healthcheck()
    if health.state != HealthState.HEALTHY:
        raise HTTPException(
            status_code=422,
            detail=f"Adapter healthcheck failed: {health.reason or health.state.value}",
        )
    try:
        profile = ProviderProfile(body.profile)
    except ValueError:
        profile = ProviderProfile.MANAGED_VENDOR
    try:
        api_type = EndpointApiType("openai_native")
    except ValueError:
        api_type = EndpointApiType.OPENAI_NATIVE
    record = ProviderRecord(
        provider_id=body.provider_id,
        display_name=body.display_name,
        adapter_class=canonical_ref,
        enabled=True,
        profile=profile,
        priority=100,
        endpoint=EndpointConfig(base_url=body.base_url, api_type=api_type),
        auth=AuthConfig(type="api_key", api_key_env_var=body.api_key_env_var),
        model_defaults=ModelDefaults(model=body.model),
    )
    registry.register(record, adapter)
    persisted = PersistedProviderRecord(
        provider_id=body.provider_id,
        display_name=body.display_name,
        adapter_class=canonical_ref,
        enabled=True,
        profile=profile.value,
        priority=100,
        endpoint_base_url=body.base_url,
        endpoint_api_type=api_type.value,
        auth_type="api_key",
        auth_api_key_env_var=body.api_key_env_var,
        model=body.model,
    )
    await store.save_provider(persisted)
    return ProviderRegisterResponse(
        provider_id=body.provider_id,
        display_name=body.display_name,
        enabled=True,
        profile=profile.value,
    )


@router.delete("/providers/{provider_id}", status_code=204)
async def unregister_provider(
    provider_id: str,
    request: Request,
    force_drain: bool = False,
    _identity: IdentityContext = Depends(require_valid_identity),
) -> None:
    """Unregister a provider. Returns 409 if active sessions use this provider."""
    store = _get_provider_store(request)
    if store is None:
        raise HTTPException(
            status_code=503,
            detail="Provider store is not configured (memory backend).",
        )
    registry = _get_provider_registry(request)
    session_store = _get_session_store(request)
    if session_store is not None:
        count = await session_store.count_active_sessions_by_provider(provider_id)
        if count > 0:
            if force_drain:
                if not _can_use_provider_drain(request, _identity):
                    raise HTTPException(
                        status_code=403,
                        detail=(
                            "Graceful drain is disabled or caller lacks admin role required "
                            "for provider-drain override."
                        ),
                    )
                drain_fn = getattr(session_store, "deactivate_sessions_by_provider", None)
                if not callable(drain_fn):
                    raise HTTPException(
                        status_code=422,
                        detail="Session store does not support provider-drain operation.",
                    )
                _ = await drain_fn(provider_id)
                tenant_factory = getattr(request.app.state, "tenant_factory", None)
                if tenant_factory is not None and hasattr(tenant_factory, "evict_sessions_for_provider"):
                    tenant_factory.evict_sessions_for_provider(provider_id)
                count = await session_store.count_active_sessions_by_provider(provider_id)
                if count == 0:
                    pass
                else:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            f"Cannot delete provider '{provider_id}': {count} active session(s) "
                            "remain after attempted drain."
                        ),
                    )
            else:
                raise HTTPException(
                    status_code=409,
                    detail=f"Cannot delete provider '{provider_id}': {count} active session(s) depend on it.",
                )
    in_registry = provider_id in registry._providers
    persisted = await store.get_provider(provider_id)
    in_store = persisted is not None
    if not in_registry and not in_store:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' not found")
    if in_registry:
        registry.unregister(provider_id)
    if in_store:
        await store.delete_provider(provider_id)
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
