"""
File: service.py
Path: src/modules/platform_bootstrap/service.py
Role: Build the modular-monolith service container and validate environment-sensitive bootstrap settings.
Used By:
 - src/api/app.py
 - src/api/bootstrap.py
 - src/api/dependencies.py
Depends On:
 - src/config/provider_registry.py
 - src/config/settings.py
 - src/modules/agent_management/service.py
 - src/modules/audit_observability/service.py
 - src/modules/identity_access/service.py
 - src/modules/provider_management/service.py
 - src/modules/session_runtime/service.py
 - src/modules/tenant_governance/service.py
 - src/modules/tool_management/service.py
Notes:
 - Dev/test may use OpenAI defaults; non-dev environments must declare their bootstrap provider explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

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
from src.modules.agent_management.service import AgentManagementModule
from src.modules.audit_observability.service import AuditObservabilityModule
from src.modules.identity_access.service import IdentityAccessModule, IdentityAccessService
from src.modules.provider_management.service import ProviderManagementModule, ProviderManagementService
from src.modules.session_runtime.service import SessionRuntimeModule, SessionRuntimeService
from src.modules.tenant_governance.service import TenantGovernanceModule
from src.modules.tool_management.service import ToolManagementModule
from src.observability.ingress_budget import IngressBudgetRecorder
from src.observability.logging import StructuredLogger
from src.observability.tool_audit import ToolAuditPipeline
from src.runtime.adapter_factory import OPENAI_ADAPTER_CANONICAL_CLASS_REF, canonicalize_adapter_class_ref, load_adapter


DEVELOPMENT_ENVIRONMENTS = {"development", "test"}
DEV_SECRET_DEFAULTS = {
    "EXO_BYOC_WORKER_JWT_SECRET": "exo-byoc-dev-secret",
    "EXO_TOOL_ARTIFACT_SIGNING_SECRET": "exo-tool-artifact-dev-secret",
    "EXO_AUDIT_BUNDLE_SIGNING_SECRET": "exo-audit-dev-secret",
}


@dataclass(slots=True)
class PlatformBootstrapModule:
    settings: AppSettings
    persistence_backend: str


@dataclass(slots=True)
class AppModules:
    platform_bootstrap: PlatformBootstrapModule
    identity_access: IdentityAccessModule
    tenant_governance: TenantGovernanceModule
    provider_management: ProviderManagementModule
    agent_management: AgentManagementModule
    tool_management: ToolManagementModule
    session_runtime: SessionRuntimeModule
    audit_observability: AuditObservabilityModule


_MISSING = object()
_COMPAT_STATE_FIELDS = (
    "settings",
    "tenant_factory",
    "provider_registry",
    "session_store",
    "run_control_registry",
    "tool_audit_pipeline",
    "audit_store",
    "tool_artifact_store",
)


def _is_mock_like(value: object) -> bool:
    return value.__class__.__module__.startswith("unittest.mock")


def _state_attr(state: object, name: str, default: Any = None) -> Any:
    if state is None:
        return default
    if _is_mock_like(state) and name not in getattr(state, "__dict__", {}):
        return default
    value = getattr(state, name, _MISSING)
    if value is _MISSING:
        return default
    return value


def _default_test_settings() -> AppSettings:
    return AppSettings(
        schema_version="1.0",
        environment="test",
        runtime=RuntimeSettings(
            default_provider_id="openai-test",
            allowed_provider_ids=["openai-test"],
            require_provider_healthcheck_on_start=False,
        ),
    )


def _settings_auth_value(settings: object, name: str, default: Any) -> Any:
    auth = getattr(settings, "auth", None)
    return getattr(auth, name, default) if auth is not None else default


def _settings_limits_value(settings: object, name: str, default: Any) -> Any:
    limits = getattr(settings, "limits", None)
    return getattr(limits, name, default) if limits is not None else default


def _sync_identity_access_from_settings(service: IdentityAccessService, settings: object) -> None:
    auth = getattr(settings, "auth", None)
    if auth is None:
        service.allow_cross_tenant_admin = False
        service.cross_tenant_admin_roles = ("super_admin",)
        return
    roles = tuple(
        str(role).strip()
        for role in getattr(auth, "cross_tenant_admin_roles", ["super_admin"])
        if str(role).strip()
    )
    service.allow_cross_tenant_admin = bool(getattr(auth, "allow_cross_tenant_admin", False))
    service.cross_tenant_admin_roles = roles


def _sync_modules_from_state(modules: AppModules, state: object) -> AppModules:
    settings = _state_attr(state, "settings", modules.platform_bootstrap.settings)
    modules.platform_bootstrap.settings = settings

    modules.identity_access.service.api_key_store = _state_attr(
        state,
        "api_key_store",
        modules.identity_access.service.api_key_store,
    )
    _sync_identity_access_from_settings(modules.identity_access.service, settings)

    modules.tenant_governance.policy_overlay_store = _state_attr(
        state,
        "policy_overlay_store",
        modules.tenant_governance.policy_overlay_store,
    )
    modules.tenant_governance.turn_rate_limiter = _state_attr(
        state,
        "turn_rate_limiter",
        modules.tenant_governance.turn_rate_limiter,
    )
    modules.tenant_governance.tool_upload_rate_limiter = _state_attr(
        state,
        "tool_upload_rate_limiter",
        modules.tenant_governance.tool_upload_rate_limiter,
    )

    provider_registry = _state_attr(state, "provider_registry", modules.provider_management.registry)
    provider_store = _state_attr(state, "provider_store", modules.provider_management.store)
    modules.provider_management.registry = provider_registry
    modules.provider_management.store = provider_store
    modules.provider_management.service.registry = provider_registry
    modules.provider_management.service.store = provider_store

    modules.agent_management.agent_store = _state_attr(
        state,
        "agent_store",
        modules.agent_management.agent_store,
    )

    modules.tool_management.tool_store = _state_attr(
        state,
        "tool_store",
        modules.tool_management.tool_store,
    )
    modules.tool_management.tool_version_store = _state_attr(
        state,
        "tool_version_store",
        modules.tool_management.tool_version_store,
    )
    modules.tool_management.tool_artifact_store = _state_attr(
        state,
        "tool_artifact_store",
        modules.tool_management.tool_artifact_store,
    )
    modules.tool_management.artifact_signing_secret = str(
        _settings_limits_value(
            settings,
            "tool_artifact_signing_secret",
            modules.tool_management.artifact_signing_secret,
        )
        or ""
    )

    tenant_factory = _state_attr(state, "tenant_factory", modules.session_runtime.tenant_factory)
    session_store = _state_attr(state, "session_store", modules.session_runtime.session_store)
    run_control_registry = _state_attr(
        state,
        "run_control_registry",
        modules.session_runtime.run_control_registry,
    )
    turn_rate_limiter = _state_attr(
        state,
        "turn_rate_limiter",
        modules.session_runtime.turn_rate_limiter,
    )
    tool_upload_rate_limiter = _state_attr(
        state,
        "tool_upload_rate_limiter",
        modules.session_runtime.tool_upload_rate_limiter,
    )

    modules.session_runtime.tenant_factory = tenant_factory
    modules.session_runtime.session_store = session_store
    modules.session_runtime.run_control_registry = run_control_registry
    modules.session_runtime.turn_rate_limiter = turn_rate_limiter
    modules.session_runtime.tool_upload_rate_limiter = tool_upload_rate_limiter
    modules.session_runtime.service.tenant_factory = tenant_factory
    modules.session_runtime.service.session_store = session_store
    modules.session_runtime.service.run_control_registry = run_control_registry
    modules.session_runtime.service.turn_rate_limiter = turn_rate_limiter
    modules.session_runtime.service.tool_upload_rate_limiter = tool_upload_rate_limiter
    if tenant_factory is not None:
        if hasattr(tenant_factory, "_session_store"):
            tenant_factory._session_store = session_store
        context_builder = getattr(tenant_factory, "_context_builder", None)
        if context_builder is not None and hasattr(context_builder, "_session_store"):
            context_builder._session_store = session_store

    modules.audit_observability.audit_store = _state_attr(
        state,
        "audit_store",
        modules.audit_observability.audit_store,
    )
    modules.audit_observability.tool_audit_pipeline = _state_attr(
        state,
        "tool_audit_pipeline",
        modules.audit_observability.tool_audit_pipeline,
    )
    modules.audit_observability.structured_logger = _state_attr(
        state,
        "structured_logger",
        modules.audit_observability.structured_logger,
    )
    modules.audit_observability.ingress_budget_recorder = _state_attr(
        state,
        "ingress_budget_recorder",
        modules.audit_observability.ingress_budget_recorder,
    )
    modules.audit_observability.audit_export_directory = Path(
        str(
            _settings_limits_value(
                settings,
                "audit_export_directory",
                modules.audit_observability.audit_export_directory,
            )
        )
    )
    modules.audit_observability.max_audit_records_per_tenant = int(
        _settings_limits_value(
            settings,
            "max_audit_records_per_tenant",
            modules.audit_observability.max_audit_records_per_tenant,
        )
    )
    modules.audit_observability.max_audit_export_records = int(
        _settings_limits_value(
            settings,
            "max_audit_export_records",
            modules.audit_observability.max_audit_export_records,
        )
    )
    modules.audit_observability.audit_bundle_signing_secret = str(
        _settings_limits_value(
            settings,
            "audit_bundle_signing_secret",
            modules.audit_observability.audit_bundle_signing_secret,
        )
        or ""
    )
    modules.audit_observability.audit_bundle_signing_active_version = str(
        _settings_limits_value(
            settings,
            "audit_bundle_signing_active_version",
            modules.audit_observability.audit_bundle_signing_active_version,
        )
        or "v1"
    )
    secrets_by_version = _settings_limits_value(
        settings,
        "audit_bundle_signing_secrets_by_version",
        modules.audit_observability.audit_bundle_signing_secrets_by_version,
    )
    modules.audit_observability.audit_bundle_signing_secrets_by_version = dict(secrets_by_version or {})
    return modules


def _build_compat_modules_from_state(state: object) -> AppModules:
    settings = _state_attr(state, "settings", _default_test_settings())
    identity_service = IdentityAccessService(api_key_store=_state_attr(state, "api_key_store", None))
    _sync_identity_access_from_settings(identity_service, settings)
    modules = AppModules(
        platform_bootstrap=PlatformBootstrapModule(
            settings=settings,
            persistence_backend=str(_state_attr(state, "persistence_backend", "memory") or "memory"),
        ),
        identity_access=IdentityAccessModule(service=identity_service),
        tenant_governance=TenantGovernanceModule(
            policy_overlay_store=_state_attr(state, "policy_overlay_store", None),
            turn_rate_limiter=_state_attr(state, "turn_rate_limiter", None),
            tool_upload_rate_limiter=_state_attr(state, "tool_upload_rate_limiter", None),
        ),
        provider_management=ProviderManagementModule(
            service=ProviderManagementService(
                registry=_state_attr(state, "provider_registry", None),
                store=_state_attr(state, "provider_store", None),
                identity_access=identity_service,
            ),
            registry=_state_attr(state, "provider_registry", None),
            store=_state_attr(state, "provider_store", None),
        ),
        agent_management=AgentManagementModule(
            agent_store=_state_attr(state, "agent_store", None),
        ),
        tool_management=ToolManagementModule(
            tool_store=_state_attr(state, "tool_store", None),
            tool_version_store=_state_attr(state, "tool_version_store", None),
            tool_artifact_store=_state_attr(state, "tool_artifact_store", None),
            artifact_signing_secret=str(_settings_limits_value(settings, "tool_artifact_signing_secret", "") or ""),
        ),
        session_runtime=SessionRuntimeModule(
            service=SessionRuntimeService(
                tenant_factory=_state_attr(state, "tenant_factory", None),
                session_store=_state_attr(state, "session_store", None),
                run_control_registry=_state_attr(state, "run_control_registry", None),
                turn_rate_limiter=_state_attr(state, "turn_rate_limiter", None),
                tool_upload_rate_limiter=_state_attr(state, "tool_upload_rate_limiter", None),
            ),
            tenant_factory=_state_attr(state, "tenant_factory", None),
            session_store=_state_attr(state, "session_store", None),
            run_control_registry=_state_attr(state, "run_control_registry", None),
            turn_rate_limiter=_state_attr(state, "turn_rate_limiter", None),
            tool_upload_rate_limiter=_state_attr(state, "tool_upload_rate_limiter", None),
        ),
        audit_observability=AuditObservabilityModule(
            audit_store=_state_attr(state, "audit_store", None),
            tool_audit_pipeline=_state_attr(state, "tool_audit_pipeline", None),
            structured_logger=_state_attr(state, "structured_logger", None),
            ingress_budget_recorder=_state_attr(state, "ingress_budget_recorder", None),
            audit_export_directory=Path(str(_settings_limits_value(settings, "audit_export_directory", ".exo_data/audit_exports"))),
            max_audit_records_per_tenant=int(_settings_limits_value(settings, "max_audit_records_per_tenant", 10_000)),
            max_audit_export_records=int(_settings_limits_value(settings, "max_audit_export_records", 2_000)),
            audit_bundle_signing_secret=str(_settings_limits_value(settings, "audit_bundle_signing_secret", "") or ""),
            audit_bundle_signing_active_version=str(
                _settings_limits_value(settings, "audit_bundle_signing_active_version", "v1") or "v1"
            ),
            audit_bundle_signing_secrets_by_version=dict(
                _settings_limits_value(settings, "audit_bundle_signing_secrets_by_version", {}) or {}
            ),
        ),
    )
    return _sync_modules_from_state(modules, state)


def _has_compat_state_data(state: object) -> bool:
    return any(_state_attr(state, name, _MISSING) is not _MISSING for name in _COMPAT_STATE_FIELDS)


def app_modules_from_state(state) -> AppModules | None:
    modules = _state_attr(state, "modules", None)
    if isinstance(modules, AppModules):
        return _sync_modules_from_state(modules, state)
    if state is None or not _has_compat_state_data(state):
        return None
    return _build_compat_modules_from_state(state)


def app_modules_from_requestlike(requestlike) -> AppModules | None:
    app = getattr(requestlike, "app", requestlike)
    state = getattr(app, "state", None)
    if state is None:
        return None
    return app_modules_from_state(state)


def validate_non_dev_secrets(settings: AppSettings) -> None:
    environment = str(getattr(settings, "environment", "")).strip().lower()
    if environment in DEVELOPMENT_ENVIRONMENTS:
        return

    invalid: list[str] = []
    values = {
        "EXO_BYOC_WORKER_JWT_SECRET": str(getattr(settings.runtime, "byoc_worker_jwt_secret", "") or "").strip(),
        "EXO_TOOL_ARTIFACT_SIGNING_SECRET": str(
            getattr(settings.limits, "tool_artifact_signing_secret", "") or ""
        ).strip(),
        "EXO_AUDIT_BUNDLE_SIGNING_SECRET": str(
            getattr(settings.limits, "audit_bundle_signing_secret", "") or ""
        ).strip(),
    }
    for env_name, current_value in values.items():
        if not current_value or current_value == DEV_SECRET_DEFAULTS[env_name]:
            invalid.append(env_name)
    if invalid:
        joined = ", ".join(sorted(invalid))
        raise ValueError(
            f"Refusing to start with missing or development-only signing secrets in environment='{environment}': {joined}"
        )

    jwks_url = str(getattr(settings.auth, "jwks_url", "") or "").strip()
    jwt_secret = str(getattr(settings.auth, "jwt_secret", "") or "").strip()
    if jwt_secret and not jwks_url and len(jwt_secret) < 32:
        raise ValueError(
            "Refusing to start: EXO_AUTH_JWT_SECRET must be at least 32 characters when EXO_AUTH_JWKS_URL is unset "
            f"(environment='{environment}')."
        )


def build_default_provider_registry(settings: AppSettings) -> ProviderRegistry:
    environment = str(getattr(settings, "environment", "")).strip().lower()
    dev_mode = environment in DEVELOPMENT_ENVIRONMENTS
    provider_id = str(settings.runtime.default_provider_id).strip()
    adapter_class_ref = str(os.environ.get("EXO_DEFAULT_PROVIDER_ADAPTER_CLASS", "")).strip()
    if not adapter_class_ref:
        if dev_mode:
            adapter_class_ref = OPENAI_ADAPTER_CANONICAL_CLASS_REF
        else:
            raise ValueError(
                "EXO_DEFAULT_PROVIDER_ADAPTER_CLASS must be configured outside development/test bootstrap."
            )

    api_type_raw = str(os.environ.get("EXO_DEFAULT_PROVIDER_API_TYPE", "")).strip().lower()
    if not api_type_raw:
        if dev_mode:
            api_type_raw = EndpointApiType.OPENAI_NATIVE.value
        else:
            raise ValueError("EXO_DEFAULT_PROVIDER_API_TYPE must be configured outside development/test bootstrap.")
    try:
        api_type = EndpointApiType(api_type_raw)
    except ValueError as exc:
        raise ValueError(f"Unsupported EXO_DEFAULT_PROVIDER_API_TYPE '{api_type_raw}'.") from exc

    base_url = str(os.environ.get("EXO_DEFAULT_PROVIDER_BASE_URL", "")).strip()
    if not base_url:
        if dev_mode and api_type == EndpointApiType.OPENAI_NATIVE:
            base_url = "https://api.openai.com"
        else:
            raise ValueError("EXO_DEFAULT_PROVIDER_BASE_URL must be configured outside development/test bootstrap.")

    model = str(os.environ.get("EXO_DEFAULT_PROVIDER_MODEL", "")).strip()
    if not model:
        if dev_mode:
            model = "gpt-4o-mini"
        else:
            raise ValueError("EXO_DEFAULT_PROVIDER_MODEL must be configured outside development/test bootstrap.")

    api_key_env_var = str(os.environ.get("EXO_DEFAULT_PROVIDER_API_KEY_ENV_VAR", "")).strip()
    if not api_key_env_var and dev_mode and api_type == EndpointApiType.OPENAI_NATIVE:
        api_key_env_var = "OPENAI_API_KEY"

    canonical_ref = canonicalize_adapter_class_ref(adapter_class_ref)
    adapter = load_adapter(canonical_ref, provider_id=provider_id)
    record = ProviderRecord(
        provider_id=provider_id,
        display_name=f"{provider_id} (default)",
        adapter_class=canonical_ref,
        enabled=True,
        profile=ProviderProfile.MANAGED_VENDOR,
        priority=1,
        endpoint=EndpointConfig(base_url=base_url, api_type=api_type),
        auth=AuthConfig(type="api_key", api_key_env_var=api_key_env_var),
        model_defaults=ModelDefaults(model=model),
    )
    return ProviderRegistry(settings=settings, providers=[record], adapters={provider_id: adapter})


def build_app_modules(
    *,
    settings: AppSettings,
    persistence_backend: str,
    provider_registry: ProviderRegistry,
    tenant_factory,
    policy_overlay_store,
    tool_store,
    agent_store,
    api_key_store,
    provider_store,
    tool_version_store,
    session_store,
    run_control_registry,
    turn_rate_limiter,
    tool_upload_rate_limiter,
    structured_logger: StructuredLogger,
    audit_store,
    tool_audit_pipeline: ToolAuditPipeline,
    ingress_budget_recorder: IngressBudgetRecorder,
    tool_artifact_store,
) -> AppModules:
    identity_service = IdentityAccessService(
        api_key_store=api_key_store,
        allow_cross_tenant_admin=bool(getattr(settings.auth, "allow_cross_tenant_admin", False)),
        cross_tenant_admin_roles=tuple(getattr(settings.auth, "cross_tenant_admin_roles", ["super_admin"])),
    )
    provider_service = ProviderManagementService(
        registry=provider_registry,
        store=provider_store,
        identity_access=identity_service,
    )
    session_service = SessionRuntimeService(
        tenant_factory=tenant_factory,
        session_store=session_store,
        run_control_registry=run_control_registry,
        turn_rate_limiter=turn_rate_limiter,
        tool_upload_rate_limiter=tool_upload_rate_limiter,
    )
    return AppModules(
        platform_bootstrap=PlatformBootstrapModule(settings=settings, persistence_backend=persistence_backend),
        identity_access=IdentityAccessModule(service=identity_service),
        tenant_governance=TenantGovernanceModule(
            policy_overlay_store=policy_overlay_store,
            turn_rate_limiter=turn_rate_limiter,
            tool_upload_rate_limiter=tool_upload_rate_limiter,
        ),
        provider_management=ProviderManagementModule(
            service=provider_service,
            registry=provider_registry,
            store=provider_store,
        ),
        agent_management=AgentManagementModule(agent_store=agent_store),
        tool_management=ToolManagementModule(
            tool_store=tool_store,
            tool_version_store=tool_version_store,
            tool_artifact_store=tool_artifact_store,
            artifact_signing_secret=str(getattr(settings.limits, "tool_artifact_signing_secret", "") or ""),
        ),
        session_runtime=SessionRuntimeModule(
            service=session_service,
            tenant_factory=tenant_factory,
            session_store=session_store,
            run_control_registry=run_control_registry,
            turn_rate_limiter=turn_rate_limiter,
            tool_upload_rate_limiter=tool_upload_rate_limiter,
        ),
        audit_observability=AuditObservabilityModule(
            audit_store=audit_store,
            tool_audit_pipeline=tool_audit_pipeline,
            structured_logger=structured_logger,
            ingress_budget_recorder=ingress_budget_recorder,
            audit_export_directory=Path(
                str(getattr(settings.limits, "audit_export_directory", ".exo_data/audit_exports"))
            ),
            max_audit_records_per_tenant=int(getattr(settings.limits, "max_audit_records_per_tenant", 10_000)),
            max_audit_export_records=int(getattr(settings.limits, "max_audit_export_records", 2_000)),
            audit_bundle_signing_secret=str(getattr(settings.limits, "audit_bundle_signing_secret", "") or ""),
            audit_bundle_signing_active_version=str(
                getattr(settings.limits, "audit_bundle_signing_active_version", "v1")
            ),
            audit_bundle_signing_secrets_by_version=dict(
                getattr(settings.limits, "audit_bundle_signing_secrets_by_version", {})
            ),
        ),
    )
