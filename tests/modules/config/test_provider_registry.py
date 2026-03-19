"""
File: test_provider_registry.py
Path: tests/modules/config/test_provider_registry.py
Role: Acceptance tests for ProviderRegistry.get_adapter() — Slice 0 pre-req #1.
Used By:
 - pytest
Depends On:
 - src/config/provider_registry.py
 - src/runtime/openai_agents_runtime.py
"""

from __future__ import annotations

import asyncio
import pytest

from src.config.provider_registry import (
    AuthConfig,
    EndpointApiType,
    EndpointConfig,
    ModelDefaults,
    ProviderProfile,
    ProviderRecord,
    ProviderRegistry,
)
from src.config.settings import AppSettings, RuntimeSettings
from src.runtime.capability_map import HealthState, HealthStatus
from src.runtime.openai_agents_runtime import OpenAIAgentsRuntimeAdapter


def _make_settings(provider_id: str = "test-provider") -> AppSettings:
    return AppSettings(
        schema_version="1.0",
        environment="test",
        runtime=RuntimeSettings(
            default_provider_id=provider_id,
            allowed_provider_ids=[provider_id],
            require_provider_healthcheck_on_start=False,
        ),
    )


def _make_record(provider_id: str = "test-provider") -> ProviderRecord:
    return ProviderRecord(
        provider_id=provider_id,
        display_name="Test Provider",
        adapter_class="OpenAIAgentsRuntimeAdapter",
        enabled=True,
        profile=ProviderProfile.MANAGED_VENDOR,
        priority=1,
        endpoint=EndpointConfig(base_url="https://api.openai.com", api_type=EndpointApiType.OPENAI_NATIVE),
        auth=AuthConfig(type="api_key", api_key_env_var=""),
        model_defaults=ModelDefaults(model="gpt-4o-mini"),
    )


def test_get_adapter_returns_registered_adapter() -> None:
    adapter = OpenAIAgentsRuntimeAdapter(provider_id="test-provider")
    registry = ProviderRegistry(
        settings=_make_settings(),
        providers=[_make_record()],
        adapters={"test-provider": adapter},
    )
    result = registry.get_adapter("test-provider")
    assert result is adapter


def test_get_adapter_raises_key_error_for_unknown_provider() -> None:
    registry = ProviderRegistry(
        settings=_make_settings(),
        providers=[_make_record()],
        adapters={},
    )
    with pytest.raises(KeyError, match="No adapter bound for provider 'test-provider'"):
        registry.get_adapter("test-provider")


def test_get_adapter_raises_key_error_for_missing_key() -> None:
    registry = ProviderRegistry(
        settings=_make_settings(),
        providers=[_make_record()],
        adapters={"other-provider": OpenAIAgentsRuntimeAdapter()},
    )
    with pytest.raises(KeyError):
        registry.get_adapter("test-provider")


class _SecretsProviderDouble:
    def __init__(self, values: dict[str, str | None]) -> None:
        self._values = values

    def get(self, key: str) -> str | None:
        return self._values.get(key)


class _HealthAdapter(OpenAIAgentsRuntimeAdapter):
    def __init__(self, provider_id: str, state: HealthState) -> None:
        super().__init__(provider_id=provider_id)
        self._state = state

    async def healthcheck(self) -> HealthStatus:
        return HealthStatus(state=self._state, reason=f"state={self._state.value}")


def _make_registry(
    settings: AppSettings,
    providers: list[ProviderRecord],
    adapters: dict[str, OpenAIAgentsRuntimeAdapter],
    *,
    secrets: dict[str, str | None] | None = None,
) -> ProviderRegistry:
    return ProviderRegistry(
        settings=settings,
        providers=providers,
        adapters=adapters,
        secrets_provider=_SecretsProviderDouble(secrets or {}),
    )


def test_enabled_provider_ids_only_returns_enabled_sorted() -> None:
    disabled = _make_record("disabled-provider")
    disabled.enabled = False
    enabled = _make_record("enabled-provider")
    enabled.enabled = True
    registry = ProviderRegistry(
        settings=_make_settings("enabled-provider"),
        providers=[disabled, enabled],
        adapters={},
    )
    assert registry.enabled_provider_ids() == ["enabled-provider"]


def test_provider_register_get_and_unregister_flow() -> None:
    record = _make_record("dynamic-provider")
    adapter = OpenAIAgentsRuntimeAdapter(provider_id="dynamic-provider")
    registry = ProviderRegistry(
        settings=_make_settings("dynamic-provider"),
        providers=[],
        adapters={},
    )
    registry.register(record, adapter)
    assert registry.get("dynamic-provider") is record
    assert registry.get_adapter("dynamic-provider") is adapter
    registry.unregister("dynamic-provider")
    with pytest.raises(KeyError, match="dynamic-provider"):
        registry.get("dynamic-provider")
    with pytest.raises(KeyError, match="dynamic-provider"):
        registry.unregister("dynamic-provider")


def test_validate_startup_fails_when_default_not_registered() -> None:
    settings = _make_settings("missing-default")
    registry = _make_registry(settings, providers=[], adapters={})
    with pytest.raises(ValueError, match="default_provider_id is not registered"):
        asyncio.run(registry.validate_startup())


def test_validate_startup_fails_when_default_disabled() -> None:
    settings = _make_settings("test-provider")
    record = _make_record("test-provider")
    record.enabled = False
    registry = _make_registry(settings, providers=[record], adapters={"test-provider": OpenAIAgentsRuntimeAdapter()})
    with pytest.raises(ValueError, match="default_provider_id must be enabled"):
        asyncio.run(registry.validate_startup())


def test_validate_startup_fails_when_allowed_provider_unknown() -> None:
    settings = AppSettings(
        schema_version="1.0",
        environment="test",
        runtime=RuntimeSettings(
            default_provider_id="test-provider",
            allowed_provider_ids=["test-provider", "ghost-provider"],
            require_provider_healthcheck_on_start=False,
        ),
    )
    registry = _make_registry(
        settings,
        providers=[_make_record("test-provider")],
        adapters={"test-provider": OpenAIAgentsRuntimeAdapter()},
    )
    with pytest.raises(ValueError, match="unknown providers"):
        asyncio.run(registry.validate_startup())


def test_validate_startup_requires_secret_when_env_var_configured() -> None:
    settings = _make_settings("secret-provider")
    settings.runtime.require_provider_healthcheck_on_start = True
    record = _make_record("secret-provider")
    record.auth.api_key_env_var = "MISSING_SECRET"
    registry = _make_registry(
        settings,
        providers=[record],
        adapters={"secret-provider": _HealthAdapter("secret-provider", HealthState.HEALTHY)},
        secrets={},
    )
    with pytest.raises(ValueError, match="Missing provider secret"):
        asyncio.run(registry.validate_startup())


def test_validate_startup_fails_when_adapter_binding_missing() -> None:
    settings = _make_settings("test-provider")
    settings.runtime.require_provider_healthcheck_on_start = True
    registry = _make_registry(settings, providers=[_make_record("test-provider")], adapters={})
    with pytest.raises(ValueError, match="Missing adapter binding"):
        asyncio.run(registry.validate_startup())


def test_validate_startup_fails_when_default_unhealthy_without_fallback() -> None:
    settings = _make_settings("default-provider")
    settings.runtime.require_provider_healthcheck_on_start = True
    record = _make_record("default-provider")
    registry = _make_registry(
        settings,
        providers=[record],
        adapters={"default-provider": _HealthAdapter("default-provider", HealthState.DOWN)},
    )
    with pytest.raises(ValueError, match="no fallback is configured"):
        asyncio.run(registry.validate_startup())


def test_validate_startup_fails_when_default_unhealthy_and_fallback_adapter_missing() -> None:
    settings = _make_settings("default-provider")
    settings.runtime.require_provider_healthcheck_on_start = True
    settings.runtime.fallback_provider_id = "fallback-provider"
    default_record = _make_record("default-provider")
    fallback_record = _make_record("fallback-provider")
    registry = _make_registry(
        settings,
        providers=[default_record, fallback_record],
        adapters={"default-provider": _HealthAdapter("default-provider", HealthState.DOWN)},
    )
    with pytest.raises(ValueError, match="Fallback provider 'fallback-provider' adapter is missing"):
        asyncio.run(registry.validate_startup())


def test_validate_startup_passes_with_healthcheck_disabled() -> None:
    settings = _make_settings("test-provider")
    settings.runtime.require_provider_healthcheck_on_start = False
    registry = _make_registry(
        settings,
        providers=[_make_record("test-provider")],
        adapters={"test-provider": _HealthAdapter("test-provider", HealthState.DOWN)},
    )
    asyncio.run(registry.validate_startup())


def test_validate_startup_passes_with_default_unhealthy_and_fallback_available() -> None:
    settings = _make_settings("default-provider")
    settings.runtime.require_provider_healthcheck_on_start = True
    settings.runtime.fallback_provider_id = "fallback-provider"
    default_record = _make_record("default-provider")
    fallback_record = _make_record("fallback-provider")
    registry = _make_registry(
        settings,
        providers=[default_record, fallback_record],
        adapters={
            "default-provider": _HealthAdapter("default-provider", HealthState.DOWN),
            "fallback-provider": _HealthAdapter("fallback-provider", HealthState.HEALTHY),
        },
    )
    asyncio.run(registry.validate_startup())


def test_validate_startup_skips_healthcheck_for_disabled_allowed_provider() -> None:
    settings = _make_settings("default-provider")
    settings.runtime.require_provider_healthcheck_on_start = True
    settings.runtime.allowed_provider_ids = ["default-provider", "disabled-provider"]
    default_record = _make_record("default-provider")
    disabled_record = _make_record("disabled-provider")
    disabled_record.enabled = False
    registry = _make_registry(
        settings,
        providers=[default_record, disabled_record],
        adapters={"default-provider": _HealthAdapter("default-provider", HealthState.HEALTHY)},
    )
    asyncio.run(registry.validate_startup())


def test_validate_health_returns_for_healthy_provider() -> None:
    settings = _make_settings("test-provider")
    registry = _make_registry(
        settings,
        providers=[_make_record("test-provider")],
        adapters={"test-provider": _HealthAdapter("test-provider", HealthState.HEALTHY)},
    )
    registry._validate_health("test-provider", HealthStatus(state=HealthState.HEALTHY, reason="ok"))
