"""
File: bootstrap.py
Path: src/api/bootstrap.py
Role: Wire ProviderRegistry, TenantRuntimeFactory, and TenantPolicyOverlayStore into app.state.
Used By:
 - src/api/app.py
 - tests/modules/api/ (via build_test_app helper)
Depends On:
 - src/api/app.py
 - src/config/provider_registry.py
 - src/config/settings.py
 - src/runtime/tenant_runtime.py
 - src/tenancy/policy_overlay.py
Notes:
 - bootstrap() attaches three objects to app.state so all request handlers can access them
   via Depends() without importing global singletons.
 - For tests: call bootstrap() with mock registries; the app is fully isolated per test.
 - Provider adapters must be registered in the ProviderRegistry BEFORE bootstrap() is called.
"""

from __future__ import annotations

from fastapi import FastAPI

from src.config.provider_registry import ProviderRegistry
from src.config.settings import AppSettings
from src.runtime.tenant_runtime import TenantRuntimeFactory
from src.tenancy.policy_overlay import TenantPolicyOverlayStore


def bootstrap(
    app: FastAPI,
    provider_registry: ProviderRegistry,
    settings: AppSettings,
    policy_overlay_store: TenantPolicyOverlayStore | None = None,
) -> FastAPI:
    """Attach runtime objects to app.state and register startup/shutdown events.

    Returns the same app instance for chaining.
    """
    tenant_factory = TenantRuntimeFactory(
        provider_registry=provider_registry,
        settings=settings,
    )
    app.state.tenant_factory = tenant_factory
    app.state.provider_registry = provider_registry
    app.state.policy_overlay_store = policy_overlay_store or TenantPolicyOverlayStore()
    app.state.settings = settings
    return app


def build_test_app(
    provider_registry: ProviderRegistry | None = None,
    settings: AppSettings | None = None,
    policy_overlay_store: TenantPolicyOverlayStore | None = None,
) -> FastAPI:
    """Build a fully bootstrapped app for integration tests.

    Callers may supply mock registries; defaults create minimal in-memory stubs.
    """
    from src.api.app import create_app
    from src.config.provider_registry import (
        AuthConfig,
        EndpointApiType,
        EndpointConfig,
        ModelDefaults,
        ProviderProfile,
        ProviderRecord,
    )
    from src.config.settings import RuntimeSettings
    from src.runtime.openai_agents_runtime import OpenAIAgentsRuntimeAdapter

    if settings is None:
        settings = AppSettings(
            schema_version="1.0",
            environment="test",
            runtime=RuntimeSettings(
                default_provider_id="openai-test",
                allowed_provider_ids=["openai-test"],
                require_provider_healthcheck_on_start=False,
            ),
        )

    if provider_registry is None:
        adapter = OpenAIAgentsRuntimeAdapter(provider_id="openai-test")
        record = ProviderRecord(
            provider_id="openai-test",
            display_name="Test OpenAI",
            adapter_class="OpenAIAgentsRuntimeAdapter",
            enabled=True,
            profile=ProviderProfile.MANAGED_VENDOR,
            priority=1,
            endpoint=EndpointConfig(
                base_url="https://api.openai.com",
                api_type=EndpointApiType.OPENAI_NATIVE,
            ),
            auth=AuthConfig(type="api_key", api_key_env_var=""),
            model_defaults=ModelDefaults(model="gpt-4o-mini"),
        )
        provider_registry = ProviderRegistry(
            settings=settings,
            providers=[record],
            adapters={"openai-test": adapter},
        )

    app = create_app()
    return bootstrap(app, provider_registry, settings, policy_overlay_store)
