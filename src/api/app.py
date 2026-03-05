"""
File: app.py
Path: src/api/app.py
Role: FastAPI application factory — creates and configures the eXo-brain API.
Used By:
 - src/api/bootstrap.py
 - tests/modules/api/
Depends On:
 - fastapi
 - src/api/bootstrap.py
Notes:
 - create_app() is the single entry-point. Never instantiate FastAPI directly outside this file.
 - Routers are registered here as they are built in Slices 2–4.
 - app.state holds: tenant_factory, provider_registry, policy_overlay_store (set by bootstrap).
"""

from __future__ import annotations

import json
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.params import Depends

from src.api.bootstrap import bootstrap
from src.api.dependencies import require_tenant_scope_identity
from src.config.provider_registry import (
    AuthConfig,
    EndpointApiType,
    EndpointConfig,
    ModelDefaults,
    ProviderProfile,
    ProviderRecord,
    ProviderRegistry,
)
from src.config.settings import AppSettings, AuthSettings, DeploymentProfile, LimitsSettings, RuntimeSettings
from src.runtime.openai_agents_runtime import OpenAIAgentsRuntimeAdapter


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _resolve_deployment_profile(raw: str) -> DeploymentProfile:
    normalized = str(raw or "").strip().lower()
    if normalized == DeploymentProfile.SELF_HOSTED.value:
        return DeploymentProfile.SELF_HOSTED
    if normalized == DeploymentProfile.HYBRID.value:
        return DeploymentProfile.HYBRID
    return DeploymentProfile.MANAGED_CLOUD


def _profile_default(profile: DeploymentProfile, *, key: str, fallback: str) -> str:
    defaults = {
        DeploymentProfile.MANAGED_CLOUD: {
            "tool_artifact_directory": ".exo_data/tool_artifacts/managed_cloud",
            "audit_export_directory": ".exo_data/audit_exports/managed_cloud",
            "byoc_store_backend": "sqlite",
            "byoc_cleanup_interval_seconds": "20",
        },
        DeploymentProfile.SELF_HOSTED: {
            "tool_artifact_directory": ".exo_data/tool_artifacts/self_hosted",
            "audit_export_directory": ".exo_data/audit_exports/self_hosted",
            "byoc_store_backend": "sqlite",
            "byoc_cleanup_interval_seconds": "30",
        },
        DeploymentProfile.HYBRID: {
            "tool_artifact_directory": ".exo_data/tool_artifacts/hybrid",
            "audit_export_directory": ".exo_data/audit_exports/hybrid",
            "byoc_store_backend": "sqlite",
            "byoc_cleanup_interval_seconds": "25",
        },
    }
    return defaults.get(profile, {}).get(key, fallback)


def _default_settings() -> AppSettings:
    """Build app settings from lightweight environment defaults."""
    env = os.environ.get("EXO_ENV", "development")
    deployment_profile = _resolve_deployment_profile(os.environ.get("EXO_DEPLOYMENT_PROFILE", "managed_cloud"))
    default_provider_id = os.environ.get("EXO_DEFAULT_PROVIDER_ID", "openai")
    jwt_secret = os.environ.get("EXO_AUTH_JWT_SECRET", "")
    jwt_alg = os.environ.get("EXO_AUTH_JWT_ALGORITHM", "HS256")
    jwks_url = os.environ.get("EXO_AUTH_JWKS_URL", "")
    raw_signing_key_map = os.environ.get("EXO_AUDIT_BUNDLE_SIGNING_SECRETS_BY_VERSION", "").strip()
    parsed_signing_key_map: dict[str, str] = {}
    if raw_signing_key_map:
        try:
            loaded = json.loads(raw_signing_key_map)
            if isinstance(loaded, dict):
                parsed_signing_key_map = {
                    str(version).strip(): str(secret).strip()
                    for version, secret in loaded.items()
                    if str(version).strip() and str(secret).strip()
                }
        except json.JSONDecodeError:
            parsed_signing_key_map = {}
    return AppSettings(
        schema_version="1.0",
        environment=env,
        deployment_profile=deployment_profile,
        runtime=RuntimeSettings(
            default_provider_id=default_provider_id,
            allowed_provider_ids=[default_provider_id],
            require_provider_healthcheck_on_start=False,
            enable_hosted_tool_runtime=_env_bool("EXO_ENABLE_HOSTED_TOOL_RUNTIME", default=False),
            enable_hosted_tool_process_isolation=_env_bool(
                "EXO_ENABLE_HOSTED_TOOL_PROCESS_ISOLATION",
                default=False,
            ),
            enable_byoc_tool_runtime=_env_bool("EXO_ENABLE_BYOC_TOOL_RUNTIME", default=False),
            enable_provider_delete_graceful_drain=_env_bool(
                "EXO_ENABLE_PROVIDER_DELETE_GRACEFUL_DRAIN",
                default=False,
            ),
            byoc_worker_jwt_secret=os.environ.get("EXO_BYOC_WORKER_JWT_SECRET", "exo-byoc-dev-secret"),
            byoc_worker_token_ttl_seconds=int(os.environ.get("EXO_BYOC_WORKER_TOKEN_TTL_SECONDS", "300")),
            byoc_store_backend=os.environ.get(
                "EXO_BYOC_STORE_BACKEND",
                _profile_default(deployment_profile, key="byoc_store_backend", fallback="memory"),
            ),
            byoc_sqlite_db_path=os.environ.get("EXO_BYOC_DB_PATH", os.environ.get("EXO_DB_PATH", ".exo_data/exo.db")),
            byoc_lease_ttl_seconds=int(os.environ.get("EXO_BYOC_LEASE_TTL_SECONDS", "30")),
            byoc_replay_ttl_seconds=int(os.environ.get("EXO_BYOC_REPLAY_TTL_SECONDS", "300")),
            byoc_cleanup_interval_seconds=int(
                os.environ.get(
                    "EXO_BYOC_CLEANUP_INTERVAL_SECONDS",
                    _profile_default(deployment_profile, key="byoc_cleanup_interval_seconds", fallback="30"),
                )
            ),
            byoc_completed_ttl_seconds=int(os.environ.get("EXO_BYOC_COMPLETED_TTL_SECONDS", "3600")),
            byoc_cancelled_ttl_seconds=int(os.environ.get("EXO_BYOC_CANCELLED_TTL_SECONDS", "3600")),
            byoc_result_ttl_seconds=int(os.environ.get("EXO_BYOC_RESULT_TTL_SECONDS", "3600")),
            byoc_idempotency_ttl_seconds=int(os.environ.get("EXO_BYOC_IDEMPOTENCY_TTL_SECONDS", "3600")),
            byoc_max_completed_records=int(os.environ.get("EXO_BYOC_MAX_COMPLETED_RECORDS", "2000")),
            byoc_max_cancelled_records=int(os.environ.get("EXO_BYOC_MAX_CANCELLED_RECORDS", "2000")),
            byoc_max_result_records=int(os.environ.get("EXO_BYOC_MAX_RESULT_RECORDS", "2000")),
            byoc_max_claim_attempts_before_dlq=int(
                os.environ.get("EXO_BYOC_MAX_CLAIM_ATTEMPTS_BEFORE_DLQ", "3")
            ),
            byoc_result_conflict_strategy=os.environ.get(
                "EXO_BYOC_RESULT_CONFLICT_STRATEGY",
                "first_write_wins",
            ),
        ),
        auth=AuthSettings(
            jwt_secret=jwt_secret,
            jwks_url=jwks_url,
            algorithm=jwt_alg,
            allow_cross_tenant_admin=_env_bool("EXO_ALLOW_CROSS_TENANT_ADMIN", default=False),
            cross_tenant_admin_roles=[
                item.strip()
                for item in os.environ.get("EXO_CROSS_TENANT_ADMIN_ROLES", "super_admin").split(",")
                if item.strip()
            ],
        ),
        limits=LimitsSettings(
            max_parallel_jobs=int(os.environ.get("EXO_MAX_PARALLEL_JOBS", "20")),
            max_concurrent_risky_tools_per_session=int(
                os.environ.get("EXO_MAX_CONCURRENT_RISKY_TOOLS_PER_SESSION", "1")
            ),
            default_tool_timeout_ms=int(os.environ.get("EXO_DEFAULT_TOOL_TIMEOUT_MS", "30000")),
            max_active_runs_per_tenant=int(os.environ.get("EXO_MAX_ACTIVE_RUNS_PER_TENANT", "50")),
            max_turn_requests_per_minute_per_tenant=int(
                os.environ.get("EXO_MAX_TURN_REQUESTS_PER_MINUTE_PER_TENANT", "120")
            ),
            max_tool_uploads_per_minute_per_tenant=int(
                os.environ.get("EXO_MAX_TOOL_UPLOADS_PER_MINUTE_PER_TENANT", "30")
            ),
            max_tool_upload_size_bytes=int(os.environ.get("EXO_MAX_TOOL_UPLOAD_SIZE_BYTES", "5000000")),
            tool_artifact_directory=os.environ.get(
                "EXO_TOOL_ARTIFACT_DIRECTORY",
                _profile_default(deployment_profile, key="tool_artifact_directory", fallback=".exo_data/tool_artifacts"),
            ),
            tool_artifact_signing_secret=os.environ.get(
                "EXO_TOOL_ARTIFACT_SIGNING_SECRET",
                "exo-tool-artifact-dev-secret",
            ),
            allowed_tool_dependency_prefixes=[
                item.strip()
                for item in os.environ.get("EXO_ALLOWED_TOOL_DEPENDENCY_PREFIXES", "").split(",")
                if item.strip()
            ],
            max_audit_records_per_tenant=int(os.environ.get("EXO_MAX_AUDIT_RECORDS_PER_TENANT", "10000")),
            max_audit_export_records=int(os.environ.get("EXO_MAX_AUDIT_EXPORT_RECORDS", "2000")),
            audit_export_directory=os.environ.get(
                "EXO_AUDIT_EXPORT_DIRECTORY",
                _profile_default(deployment_profile, key="audit_export_directory", fallback=".exo_data/audit_exports"),
            ),
            audit_bundle_signing_secret=os.environ.get(
                "EXO_AUDIT_BUNDLE_SIGNING_SECRET",
                "exo-audit-dev-secret",
            ),
            audit_bundle_signing_active_version=os.environ.get(
                "EXO_AUDIT_BUNDLE_SIGNING_ACTIVE_VERSION",
                "v1",
            ),
            audit_bundle_signing_secrets_by_version=parsed_signing_key_map,
        ),
    )


def _default_provider_registry(settings: AppSettings) -> ProviderRegistry:
    provider_id = settings.runtime.default_provider_id
    adapter = OpenAIAgentsRuntimeAdapter(provider_id=provider_id)
    record = ProviderRecord(
        provider_id=provider_id,
        display_name=f"{provider_id} (default)",
        adapter_class="OpenAIAgentsRuntimeAdapter",
        enabled=True,
        profile=ProviderProfile.MANAGED_VENDOR,
        priority=1,
        endpoint=EndpointConfig(
            base_url=os.environ.get("EXO_DEFAULT_PROVIDER_BASE_URL", "https://api.openai.com"),
            api_type=EndpointApiType.OPENAI_NATIVE,
        ),
        auth=AuthConfig(
            type="api_key",
            api_key_env_var=os.environ.get("EXO_DEFAULT_PROVIDER_API_KEY_ENV_VAR", "OPENAI_API_KEY"),
        ),
        model_defaults=ModelDefaults(
            model=os.environ.get("EXO_DEFAULT_PROVIDER_MODEL", "gpt-4o-mini"),
        ),
    )
    return ProviderRegistry(settings=settings, providers=[record], adapters={provider_id: adapter})


def create_app(title: str = "eXo-brain API", version: str = "0.1.0") -> FastAPI:
    """Create and return a configured FastAPI application instance."""
    app = FastAPI(
        title=title,
        version=version,
        description=(
            "Provider-neutral AI orchestration platform. "
            "Deterministic tool execution, multi-tenant runtime isolation, "
            "SSE and WebSocket streaming."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["system"], summary="Platform health check")
    async def health() -> dict:
        return {"status": "ok", "platform": "eXo-brain"}

    # Slice 2 — Tool & Agent Management
    from src.api.routers.tools import router as tools_router
    from src.api.routers.agents import router as agents_router

    tenant_scope = [Depends(require_tenant_scope_identity)]
    app.include_router(tools_router, prefix="/tenants", dependencies=tenant_scope)
    app.include_router(agents_router, prefix="/tenants", dependencies=tenant_scope)

    # Slice 3 — Adapter Playground (sessions, turns, providers)
    from src.api.routers.sessions import router as sessions_router
    from src.api.routers.turns import router as turns_router
    from src.api.routers.providers import router as providers_router
    from src.api.routers.runtime_control import router as runtime_control_router
    from src.api.routers.audit import router as audit_router

    app.include_router(sessions_router, prefix="/tenants", dependencies=tenant_scope)
    app.include_router(turns_router, prefix="/tenants")
    app.include_router(providers_router)
    app.include_router(runtime_control_router, prefix="/tenants", dependencies=tenant_scope)
    app.include_router(audit_router, prefix="/tenants", dependencies=tenant_scope)

    # Slice 4 — Tenant Policy & Quota Management
    from src.api.routers.tenants import router as tenants_router

    app.include_router(tenants_router, prefix="/tenants", dependencies=tenant_scope)

    # Slice 1 — Auth Hardening (API key management)
    from src.api.routers.admin_keys import router as admin_keys_router

    app.include_router(admin_keys_router)

    # Slice 3 — Web UI Dashboard static files
    from src.api.routers.ui import mount_ui

    mount_ui(app)

    settings = _default_settings()
    provider_registry = _default_provider_registry(settings)
    return bootstrap(app, provider_registry=provider_registry, settings=settings, persistence_backend="sqlite")
