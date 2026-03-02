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
