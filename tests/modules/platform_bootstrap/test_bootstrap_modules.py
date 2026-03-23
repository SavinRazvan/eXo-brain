"""
File: test_bootstrap_modules.py
Path: tests/modules/platform_bootstrap/test_bootstrap_modules.py
Role: Unit tests for the platform-bootstrap module container and non-dev bootstrap validation.
Used By:
 - pytest
Depends On:
 - src/api/bootstrap.py
 - src/config/settings.py
 - src/modules/platform_bootstrap/service.py
Notes:
 - Verifies module installation and production-only bootstrap safety checks.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.api.bootstrap import bootstrap
from src.api.bootstrap import build_test_app
from src.config.provider_registry import (
    AuthConfig,
    EndpointApiType,
    EndpointConfig,
    ModelDefaults,
    ProviderProfile,
    ProviderRecord,
    ProviderRegistry,
)
from src.config.settings import AppSettings, AuthSettings, LimitsSettings, RuntimeSettings
from src.modules.platform_bootstrap.service import (
    _settings_auth_value,
    _state_attr,
    app_modules_from_requestlike,
    build_default_provider_registry,
    validate_non_dev_secrets,
)
from src.runtime.openai_agents_runtime import OpenAIAgentsRuntimeAdapter


def test_build_test_app_installs_module_container() -> None:
    app = build_test_app()

    assert hasattr(app.state, "modules")
    assert app.state.modules.provider_management.registry is app.state.provider_registry
    assert app.state.modules.session_runtime.tenant_factory is app.state.tenant_factory
    assert app.state.modules.tool_management.tool_artifact_store is app.state.tool_artifact_store


def test_validate_non_dev_secrets_rejects_dev_defaults() -> None:
    settings = AppSettings(
        schema_version="1.0",
        environment="production",
        runtime=RuntimeSettings(
            default_provider_id="prod-provider",
            allowed_provider_ids=["prod-provider"],
            require_provider_healthcheck_on_start=False,
            byoc_worker_jwt_secret="exo-byoc-dev-secret",
        ),
        limits=LimitsSettings(
            tool_artifact_signing_secret="exo-tool-artifact-dev-secret",
            audit_bundle_signing_secret="exo-audit-dev-secret",
        ),
    )

    with pytest.raises(ValueError, match="development-only signing secrets"):
        validate_non_dev_secrets(settings)


def test_validate_non_dev_secrets_rejects_short_symmetric_jwt_without_jwks() -> None:
    settings = AppSettings(
        schema_version="1.0",
        environment="production",
        runtime=RuntimeSettings(
            default_provider_id="prod-provider",
            allowed_provider_ids=["prod-provider"],
            require_provider_healthcheck_on_start=False,
            byoc_worker_jwt_secret="prod-byoc-worker-secret-value-ok",
        ),
        limits=LimitsSettings(
            tool_artifact_signing_secret="prod-tool-artifact-secret-value-ok",
            audit_bundle_signing_secret="prod-audit-bundle-secret-value-ok",
        ),
        auth=AuthSettings(jwt_secret="short", jwks_url=""),
    )

    with pytest.raises(ValueError, match="EXO_AUTH_JWT_SECRET"):
        validate_non_dev_secrets(settings)


def test_build_default_provider_registry_requires_explicit_non_dev_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    for env_name in (
        "EXO_DEFAULT_PROVIDER_ADAPTER_CLASS",
        "EXO_DEFAULT_PROVIDER_API_TYPE",
        "EXO_DEFAULT_PROVIDER_BASE_URL",
        "EXO_DEFAULT_PROVIDER_MODEL",
        "EXO_DEFAULT_PROVIDER_API_KEY_ENV_VAR",
    ):
        monkeypatch.delenv(env_name, raising=False)

    settings = AppSettings(
        schema_version="1.0",
        environment="production",
        runtime=RuntimeSettings(
            default_provider_id="prod-provider",
            allowed_provider_ids=["prod-provider"],
            require_provider_healthcheck_on_start=False,
            byoc_worker_jwt_secret="prod-worker-secret",
        ),
        limits=LimitsSettings(
            tool_artifact_signing_secret="prod-tool-secret",
            audit_bundle_signing_secret="prod-audit-secret",
        ),
    )

    with pytest.raises(ValueError, match="EXO_DEFAULT_PROVIDER_ADAPTER_CLASS"):
        build_default_provider_registry(settings)


def test_platform_bootstrap_helper_fallbacks_cover_none_state_and_missing_auth() -> None:
    assert _state_attr(None, "missing", "fallback") == "fallback"
    assert _settings_auth_value(SimpleNamespace(), "allow_cross_tenant_admin", False) is False
    assert app_modules_from_requestlike(SimpleNamespace(app=SimpleNamespace())) is None


@pytest.mark.parametrize(
    ("env_overrides", "missing_keys", "match"),
    [
        (
            {
                "EXO_DEFAULT_PROVIDER_ADAPTER_CLASS": "src.runtime.openai_agents_runtime.OpenAIAgentsRuntimeAdapter",
                "EXO_DEFAULT_PROVIDER_BASE_URL": "https://providers.example.com",
                "EXO_DEFAULT_PROVIDER_MODEL": "gpt-4.1-mini",
            },
            {"EXO_DEFAULT_PROVIDER_API_TYPE"},
            "EXO_DEFAULT_PROVIDER_API_TYPE",
        ),
        (
            {
                "EXO_DEFAULT_PROVIDER_ADAPTER_CLASS": "src.runtime.openai_agents_runtime.OpenAIAgentsRuntimeAdapter",
                "EXO_DEFAULT_PROVIDER_API_TYPE": "not-real",
                "EXO_DEFAULT_PROVIDER_BASE_URL": "https://providers.example.com",
                "EXO_DEFAULT_PROVIDER_MODEL": "gpt-4.1-mini",
            },
            set(),
            "Unsupported EXO_DEFAULT_PROVIDER_API_TYPE",
        ),
        (
            {
                "EXO_DEFAULT_PROVIDER_ADAPTER_CLASS": "src.runtime.openai_agents_runtime.OpenAIAgentsRuntimeAdapter",
                "EXO_DEFAULT_PROVIDER_API_TYPE": "openai_native",
                "EXO_DEFAULT_PROVIDER_MODEL": "gpt-4.1-mini",
            },
            {"EXO_DEFAULT_PROVIDER_BASE_URL"},
            "EXO_DEFAULT_PROVIDER_BASE_URL",
        ),
        (
            {
                "EXO_DEFAULT_PROVIDER_ADAPTER_CLASS": "src.runtime.openai_agents_runtime.OpenAIAgentsRuntimeAdapter",
                "EXO_DEFAULT_PROVIDER_API_TYPE": "openai_native",
                "EXO_DEFAULT_PROVIDER_BASE_URL": "https://providers.example.com",
            },
            {"EXO_DEFAULT_PROVIDER_MODEL"},
            "EXO_DEFAULT_PROVIDER_MODEL",
        ),
    ],
)
def test_build_default_provider_registry_rejects_other_non_dev_configuration_gaps(
    monkeypatch: pytest.MonkeyPatch,
    env_overrides: dict[str, str],
    missing_keys: set[str],
    match: str,
) -> None:
    for key in (
        "EXO_DEFAULT_PROVIDER_ADAPTER_CLASS",
        "EXO_DEFAULT_PROVIDER_API_TYPE",
        "EXO_DEFAULT_PROVIDER_BASE_URL",
        "EXO_DEFAULT_PROVIDER_MODEL",
        "EXO_DEFAULT_PROVIDER_API_KEY_ENV_VAR",
    ):
        monkeypatch.delenv(key, raising=False)
    for key, value in env_overrides.items():
        monkeypatch.setenv(key, value)
    for key in missing_keys:
        monkeypatch.delenv(key, raising=False)

    settings = AppSettings(
        schema_version="1.0",
        environment="production",
        runtime=RuntimeSettings(
            default_provider_id="prod-provider",
            allowed_provider_ids=["prod-provider"],
            require_provider_healthcheck_on_start=False,
            byoc_worker_jwt_secret="prod-worker-secret",
        ),
        limits=LimitsSettings(
            tool_artifact_signing_secret="prod-tool-secret",
            audit_bundle_signing_secret="prod-audit-secret",
        ),
    )

    with pytest.raises(ValueError, match=match):
        build_default_provider_registry(settings)


def test_bootstrap_appends_startup_handler_when_app_lacks_add_event_handler(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    class _AppWithoutAddEventHandler:
        def __init__(self) -> None:
            self.state = SimpleNamespace()
            self.router = SimpleNamespace(on_startup=[])

    settings = AppSettings(
        schema_version="1.0",
        environment="test",
        runtime=RuntimeSettings(
            default_provider_id="openai-test",
            allowed_provider_ids=["openai-test"],
            require_provider_healthcheck_on_start=False,
        ),
    )
    adapter = OpenAIAgentsRuntimeAdapter(provider_id="openai-test")
    provider_registry = ProviderRegistry(
        settings=settings,
        providers=[
            ProviderRecord(
                provider_id="openai-test",
                display_name="Test OpenAI",
                adapter_class="src.runtime.openai_agents_runtime.OpenAIAgentsRuntimeAdapter",
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
        ],
        adapters={"openai-test": adapter},
    )
    monkeypatch.setenv("EXO_DB_PATH", str(tmp_path / "bootstrap.sqlite"))

    app = _AppWithoutAddEventHandler()
    bootstrap(app, provider_registry, settings, persistence_backend="sqlite")

    assert len(app.router.on_startup) == 1


def test_bootstrap_uses_add_event_handler_when_available(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    class _AppWithAddEventHandler:
        def __init__(self) -> None:
            self.state = SimpleNamespace()
            self.router = SimpleNamespace(on_startup=[])
            self.events: list[tuple[str, object]] = []

        def add_event_handler(self, name: str, handler) -> None:
            self.events.append((name, handler))

    settings = AppSettings(
        schema_version="1.0",
        environment="test",
        runtime=RuntimeSettings(
            default_provider_id="openai-test",
            allowed_provider_ids=["openai-test"],
            require_provider_healthcheck_on_start=False,
        ),
    )
    adapter = OpenAIAgentsRuntimeAdapter(provider_id="openai-test")
    provider_registry = ProviderRegistry(
        settings=settings,
        providers=[
            ProviderRecord(
                provider_id="openai-test",
                display_name="Test OpenAI",
                adapter_class="src.runtime.openai_agents_runtime.OpenAIAgentsRuntimeAdapter",
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
        ],
        adapters={"openai-test": adapter},
    )
    monkeypatch.setenv("EXO_DB_PATH", str(tmp_path / "bootstrap-add-handler.sqlite"))

    app = _AppWithAddEventHandler()
    bootstrap(app, provider_registry, settings, persistence_backend="sqlite")

    assert len(app.events) == 1
    assert app.events[0][0] == "startup"
