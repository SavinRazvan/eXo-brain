"""
File: service.py
Path: src/modules/provider_management/service.py
Role: Public module services for provider registration, deletion, and protocol-aware records.
Used By:
 - src/modules/platform_bootstrap/service.py
 - src/api/routers/providers.py
Depends On:
 - src/config/provider_registry.py
 - src/modules/identity_access/service.py
 - src/persistence/contracts.py
 - src/runtime/adapter_factory.py
 - src/runtime/capability_map.py
Notes:
 - Provider registration is a platform-admin operation because providers are shared across tenants.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.config.provider_registry import (
    AuthConfig,
    EndpointApiType,
    EndpointConfig,
    ModelDefaults,
    ProviderProfile,
    ProviderRecord,
    ProviderRegistry,
)
from src.identity.contracts import IdentityContext
from src.modules.identity_access.service import IdentityAccessService
from src.persistence.contracts import PersistedProviderRecord, ProviderStore
from src.runtime.adapter_factory import canonicalize_adapter_class_ref, load_adapter
from src.runtime.capability_map import HealthState


@dataclass(frozen=True, slots=True)
class ProviderManagementError(Exception):
    status_code: int
    detail: str

    def __str__(self) -> str:
        return self.detail


@dataclass(slots=True)
class ProviderManagementService:
    registry: ProviderRegistry
    store: ProviderStore | None
    identity_access: IdentityAccessService

    def _require_provider_store(self) -> ProviderStore:
        if self.store is None:
            raise ProviderManagementError(
                status_code=503,
                detail="Provider store is not configured (memory backend).",
            )
        return self.store

    def require_provider_admin(self, identity: IdentityContext, *, surface: str) -> None:
        self.identity_access.require_platform_admin(identity, surface=surface)

    @staticmethod
    def _parse_api_type(api_type: str) -> EndpointApiType:
        normalized = str(api_type or "").strip().lower()
        if not normalized:
            raise ProviderManagementError(status_code=422, detail="api_type is required.")
        try:
            return EndpointApiType(normalized)
        except ValueError as exc:
            raise ProviderManagementError(
                status_code=422,
                detail=f"Unsupported api_type '{api_type}'.",
            ) from exc

    async def register_provider(
        self,
        *,
        identity: IdentityContext,
        provider_id: str,
        display_name: str,
        adapter_class_ref: str,
        api_key_env_var: str,
        base_url: str,
        model: str,
        profile: str,
        api_type: str,
    ) -> ProviderRecord:
        self.require_provider_admin(identity, surface="providers:register")
        store = self._require_provider_store()
        if provider_id in self.registry._providers:
            raise ProviderManagementError(
                status_code=409,
                detail=f"Provider '{provider_id}' is already registered.",
            )
        canonical_ref = canonicalize_adapter_class_ref(adapter_class_ref)
        try:
            adapter = load_adapter(canonical_ref, provider_id=provider_id)
        except (ValueError, ImportError) as exc:
            raise ProviderManagementError(status_code=422, detail=str(exc)) from exc

        health = await adapter.healthcheck()
        if health.state != HealthState.HEALTHY:
            raise ProviderManagementError(
                status_code=422,
                detail=f"Adapter healthcheck failed: {health.reason or health.state.value}",
            )

        try:
            resolved_profile = ProviderProfile(profile)
        except ValueError:
            resolved_profile = ProviderProfile.MANAGED_VENDOR
        resolved_api_type = self._parse_api_type(api_type)
        record = ProviderRecord(
            provider_id=provider_id,
            display_name=display_name,
            adapter_class=canonical_ref,
            enabled=True,
            profile=resolved_profile,
            priority=100,
            endpoint=EndpointConfig(base_url=base_url, api_type=resolved_api_type),
            auth=AuthConfig(type="api_key", api_key_env_var=api_key_env_var),
            model_defaults=ModelDefaults(model=model),
        )
        self.registry.register(record, adapter)
        await store.save_provider(
            PersistedProviderRecord(
                provider_id=provider_id,
                display_name=display_name,
                adapter_class=canonical_ref,
                enabled=True,
                profile=resolved_profile.value,
                priority=100,
                endpoint_base_url=base_url,
                endpoint_api_type=resolved_api_type.value,
                auth_type="api_key",
                auth_api_key_env_var=api_key_env_var,
                model=model,
            )
        )
        return record

    async def unregister_provider(
        self,
        *,
        identity: IdentityContext,
        provider_id: str,
        session_store,
        tenant_factory,
        force_drain: bool,
        drain_enabled: bool,
    ) -> None:
        self.require_provider_admin(identity, surface="providers:delete")
        store = self._require_provider_store()
        if session_store is not None:
            count = await session_store.count_active_sessions_by_provider(provider_id)
            if count > 0:
                if force_drain:
                    if not drain_enabled:
                        raise ProviderManagementError(
                            status_code=403,
                            detail=(
                                "Graceful drain is disabled or caller lacks admin role required "
                                "for provider-drain override."
                            ),
                        )
                    drain_fn = getattr(session_store, "deactivate_sessions_by_provider", None)
                    if not callable(drain_fn):
                        raise ProviderManagementError(
                            status_code=422,
                            detail="Session store does not support provider-drain operation.",
                        )
                    await drain_fn(provider_id)
                    if tenant_factory is not None and hasattr(tenant_factory, "evict_sessions_for_provider"):
                        tenant_factory.evict_sessions_for_provider(provider_id)
                    count = await session_store.count_active_sessions_by_provider(provider_id)
                    if count > 0:
                        raise ProviderManagementError(
                            status_code=409,
                            detail=(
                                f"Cannot delete provider '{provider_id}': {count} active session(s) "
                                "remain after attempted drain."
                            ),
                        )
                else:
                    raise ProviderManagementError(
                        status_code=409,
                        detail=f"Cannot delete provider '{provider_id}': {count} active session(s) depend on it.",
                    )

        in_registry = provider_id in self.registry._providers
        persisted = await store.get_provider(provider_id)
        if not in_registry and persisted is None:
            raise ProviderManagementError(status_code=404, detail=f"Provider '{provider_id}' not found")
        if in_registry:
            self.registry.unregister(provider_id)
        if persisted is not None:
            await store.delete_provider(provider_id)


@dataclass(slots=True)
class ProviderManagementModule:
    service: ProviderManagementService
    registry: ProviderRegistry
    store: ProviderStore | None
