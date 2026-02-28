"""
File: provider_registry.py
Path: src/config/provider_registry.py
Role: Provider registration and startup validation for adapter enablement.
Used By:
 - src/core/orchestrator.py
 - startup/bootstrap wiring (future)
Depends On:
 - dataclasses
 - src/runtime/runtime_adapter.py
 - src/config/settings.py
Notes:
 - Registry validation enforces provider-neutral startup safety checks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.config.settings import AppSettings
from src.runtime.capability_map import HealthState, HealthStatus
from src.runtime.runtime_adapter import RuntimeAdapter
from src.secrets.env_provider import EnvSecretsProvider
from src.secrets.provider import SecretsProvider


class ProviderProfile(str, Enum):
    MANAGED_VENDOR = "managed_vendor"
    SELF_MANAGED = "self_managed"
    LOCAL_ONLY = "local_only"


class EndpointApiType(str, Enum):
    OPENAI_NATIVE = "openai_native"
    OPENAI_COMPATIBLE = "openai_compatible"
    CUSTOM = "custom"


@dataclass(slots=True)
class EndpointConfig:
    base_url: str
    api_type: EndpointApiType


@dataclass(slots=True)
class AuthConfig:
    type: str
    api_key_env_var: str


@dataclass(slots=True)
class ModelDefaults:
    model: str
    temperature: float = 0.2
    max_output_tokens: int = 1500


@dataclass(slots=True)
class RolloutConfig:
    stage: str
    traffic_percent: int = 0


@dataclass(slots=True)
class ProviderRecord:
    provider_id: str
    display_name: str
    adapter_class: str
    enabled: bool
    profile: ProviderProfile
    priority: int
    endpoint: EndpointConfig
    auth: AuthConfig
    model_defaults: ModelDefaults
    capabilities_override: dict[str, Any] | None = None
    rollout: RolloutConfig = field(default_factory=lambda: RolloutConfig(stage="local", traffic_percent=0))


class ProviderRegistry:
    def __init__(
        self,
        settings: AppSettings,
        providers: list[ProviderRecord],
        adapters: dict[str, RuntimeAdapter],
        secrets_provider: SecretsProvider | None = None,
    ) -> None:
        self._settings = settings
        self._providers = {provider.provider_id: provider for provider in providers}
        self._adapters = adapters
        self._secrets_provider = secrets_provider or EnvSecretsProvider()

    def get(self, provider_id: str) -> ProviderRecord:
        if provider_id not in self._providers:
            raise KeyError(f"Provider '{provider_id}' is not registered")
        return self._providers[provider_id]

    def enabled_provider_ids(self) -> list[str]:
        return sorted([provider_id for provider_id, provider in self._providers.items() if provider.enabled])

    async def validate_startup(self) -> None:
        runtime = self._settings.runtime
        if runtime.default_provider_id not in self._providers:
            raise ValueError("default_provider_id is not registered")

        enabled_ids = set(self.enabled_provider_ids())
        if runtime.default_provider_id not in enabled_ids:
            raise ValueError("default_provider_id must be enabled")

        missing_allowed = set(runtime.allowed_provider_ids) - set(self._providers.keys())
        if missing_allowed:
            raise ValueError(f"allowed_provider_ids contain unknown providers: {sorted(missing_allowed)}")

        if not runtime.require_provider_healthcheck_on_start:
            return

        active_ids = set(runtime.allowed_provider_ids)
        active_ids.add(runtime.default_provider_id)
        for provider_id in active_ids:
            if provider_id not in enabled_ids:
                continue
            provider = self._providers[provider_id]
            if provider.auth.api_key_env_var:
                api_key = self._secrets_provider.get(provider.auth.api_key_env_var)
                if api_key is None:
                    raise ValueError(
                        f"Missing provider secret for '{provider_id}' from '{provider.auth.api_key_env_var}'"
                    )
            adapter = self._adapters.get(provider_id)
            if adapter is None:
                raise ValueError(f"Missing adapter binding for provider '{provider_id}'")
            health = await adapter.healthcheck()
            self._validate_health(provider_id, health)

    def _validate_health(self, provider_id: str, health: HealthStatus) -> None:
        if health.state == HealthState.HEALTHY:
            return

        fallback_id = self._settings.runtime.fallback_provider_id
        if provider_id == self._settings.runtime.default_provider_id:
            if fallback_id is None:
                raise ValueError(f"Default provider '{provider_id}' is not healthy and no fallback is configured")
            fallback_adapter = self._adapters.get(fallback_id)
            if fallback_adapter is None:
                raise ValueError(f"Fallback provider '{fallback_id}' adapter is missing")
