"""
File: bootstrap.py
Path: src/api/bootstrap.py
Role: Wire ProviderRegistry, TenantRuntimeFactory, persistence stores, and startup hydration into app.state.
Used By:
 - src/api/app.py
 - tests/modules/api/ (via build_test_app helper)
Depends On:
 - src/api/app.py
 - src/api/startup.py
 - src/config/provider_registry.py
 - src/config/settings.py
 - src/runtime/tenant_runtime.py
 - src/tenancy/policy_overlay.py
 - src/persistence/adapters/sqlite.py
Notes:
 - bootstrap() attaches runtime objects + persistence stores to app.state.
 - For tests: call build_test_app() which uses persistence_backend="memory" (no SQLite).
 - Provider adapters must be registered in the ProviderRegistry BEFORE bootstrap() is called.
 - EXO_DB_PATH env var controls the SQLite file path (default: .exo_data/exo.db).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from fastapi import FastAPI

from src.config.provider_registry import ProviderRegistry
from src.config.settings import AppSettings
from src.persistence.contracts import AgentStore, ToolStore
from src.runtime.tenant_runtime import TenantRuntimeFactory
from src.tenancy.policy_overlay import TenantPolicyOverlayStore


def bootstrap(
    app: FastAPI,
    provider_registry: ProviderRegistry,
    settings: AppSettings,
    policy_overlay_store: TenantPolicyOverlayStore | None = None,
    persistence_backend: Literal["sqlite", "memory"] = "sqlite",
) -> FastAPI:
    """Attach runtime objects and persistence stores to app.state, register startup hook.

    Returns the same app instance for chaining.
    """
    tool_store: ToolStore | None = None
    agent_store: AgentStore | None = None
    session_store = None

    if persistence_backend == "sqlite":
        from src.persistence.adapters.sqlite import (
            SQLiteAgentStore,
            SQLiteSessionStore,
            SQLiteToolStore,
        )

        db_path_str = os.environ.get("EXO_DB_PATH", ".exo_data/exo.db")
        db_path = Path(db_path_str)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        session_store = SQLiteSessionStore(db_path)
        tool_store = SQLiteToolStore(db_path)
        agent_store = SQLiteAgentStore(db_path)

    tenant_factory = TenantRuntimeFactory(
        provider_registry=provider_registry,
        settings=settings,
        session_store=session_store,
    )

    app.state.tenant_factory = tenant_factory
    app.state.provider_registry = provider_registry
    app.state.policy_overlay_store = policy_overlay_store or TenantPolicyOverlayStore()
    app.state.settings = settings
    app.state.tool_store = tool_store
    app.state.agent_store = agent_store

    if persistence_backend == "sqlite":
        from src.api.startup import hydrate_tenant_registries

        async def _hydrate_on_startup() -> None:
            await hydrate_tenant_registries(app)

        app.add_event_handler("startup", _hydrate_on_startup)

    return app


def build_test_app(
    provider_registry: ProviderRegistry | None = None,
    settings: AppSettings | None = None,
    policy_overlay_store: TenantPolicyOverlayStore | None = None,
) -> FastAPI:
    """Build a fully bootstrapped app for integration tests.

    Uses in-memory persistence so tests are fast and isolated.
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
    return bootstrap(app, provider_registry, settings, policy_overlay_store, persistence_backend="memory")
