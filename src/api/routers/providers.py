"""
File: providers.py
Path: src/api/routers/providers.py
Role: Provider listing, health, and capabilities endpoints.
Used By:
 - src/api/app.py
Depends On:
 - src/api/dependencies.py
 - src/api/schemas/provider_schemas.py
 - src/config/provider_registry.py
 - src/runtime/capability_map.py
Notes:
 - Provider endpoints are tenant-agnostic — providers are shared across all tenants.
 - Healthcheck calls the live adapter's healthcheck() coroutine; may take up to adapter timeout.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from src.api.dependencies import require_valid_identity
from src.api.schemas.provider_schemas import (
    ProviderCapabilitiesResponse,
    ProviderHealthResponse,
    ProviderListResponse,
    ProviderSummaryResponse,
)
from src.identity.contracts import IdentityContext

router = APIRouter(tags=["providers"])


def _get_provider_registry(request: Request):
    return request.app.state.provider_registry


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
