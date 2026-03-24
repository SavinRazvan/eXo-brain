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

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.params import Depends
from fastapi.responses import JSONResponse

from src.api.bootstrap import bootstrap
from src.api.readiness import readiness_snapshot
from src.api.dependencies import require_tenant_scope_identity
from src.config.provider_registry import ProviderRegistry
from src.config.settings import (
    AppSettings,
    AuthSettings,
    DeploymentProfile,
    LimitsSettings,
    PolicySettings,
    RuntimeSettings,
)
from src.modules.platform_bootstrap.service import build_default_provider_registry, validate_non_dev_secrets


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _control_state_backend_from_env() -> str:
    """Resolve EXO_CONTROL_STATE_BACKEND to memory|sqlite (unknown values → memory)."""
    raw = os.environ.get("EXO_CONTROL_STATE_BACKEND", "memory")
    normalized = str(raw or "").strip().lower()
    if normalized == "sqlite":
        return "sqlite"
    return "memory"


def _env_int_non_negative(name: str, default: int) -> int:
    """Parse int from env; empty/invalid → default; negative values clamp to 0."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    text = str(raw).strip()
    if not text:
        return default
    try:
        value = int(text)
    except ValueError:
        return default
    return max(0, value)


def _control_state_sqlite_db_path_from_env() -> str:
    """Default matches RuntimeSettings.control_state_sqlite_db_path when env unset or blank."""
    raw = os.environ.get("EXO_CONTROL_STATE_SQLITE_DB_PATH")
    if raw is None:
        return ".exo_data/exo_control_state.db"
    stripped = str(raw).strip()
    return stripped if stripped else ".exo_data/exo_control_state.db"


def _cors_origins_for_environment(exo_env: str) -> list[str]:
    raw = os.environ.get("EXO_CORS_ORIGINS", "").strip()
    if raw:
        return [part.strip() for part in raw.split(",") if part.strip()]
    if exo_env in ("development", "test"):
        return ["*"]
    return []


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
    raw_budget_partition_limits = os.environ.get("EXO_BYOC_BUDGET_PARTITION_LIMITS_MICROUNITS_JSON", "").strip()
    parsed_budget_partition_limits: dict[str, int] = {}
    if raw_budget_partition_limits:
        try:
            loaded_limits = json.loads(raw_budget_partition_limits)
            if isinstance(loaded_limits, dict):
                for key, value in loaded_limits.items():
                    normalized_key = str(key).strip().lower()
                    if not normalized_key:
                        continue
                    try:
                        parsed_budget_partition_limits[normalized_key] = max(int(value), 0)
                    except (TypeError, ValueError):
                        continue
        except json.JSONDecodeError:
            parsed_budget_partition_limits = {}
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
            byoc_cost_limit_microunits_per_tenant=int(
                os.environ.get("EXO_BYOC_COST_LIMIT_MICROUNITS_PER_TENANT", "1000000")
            ),
            byoc_enforce_cost_limit=_env_bool("EXO_BYOC_ENFORCE_COST_LIMIT", default=False),
            byoc_enable_cost_window_policy=_env_bool("EXO_BYOC_ENABLE_COST_WINDOW_POLICY", default=False),
            byoc_cost_window_seconds=int(os.environ.get("EXO_BYOC_COST_WINDOW_SECONDS", "3600")),
            byoc_cost_success_microunits=int(os.environ.get("EXO_BYOC_COST_SUCCESS_MICROUNITS", "100")),
            byoc_cost_error_microunits=int(os.environ.get("EXO_BYOC_COST_ERROR_MICROUNITS", "40")),
            byoc_cost_timeout_microunits=int(os.environ.get("EXO_BYOC_COST_TIMEOUT_MICROUNITS", "60")),
            byoc_cost_cancelled_microunits=int(os.environ.get("EXO_BYOC_COST_CANCELLED_MICROUNITS", "20")),
            byoc_budget_partition_scope=os.environ.get("EXO_BYOC_BUDGET_PARTITION_SCOPE", "tenant"),
            byoc_budget_partition_limits_microunits=parsed_budget_partition_limits,
            byoc_anomaly_detection_enabled=_env_bool("EXO_BYOC_ANOMALY_DETECTION_ENABLED", default=True),
            byoc_anomaly_cost_utilization_threshold=float(
                os.environ.get("EXO_BYOC_ANOMALY_COST_UTILIZATION_THRESHOLD", "0.9")
            ),
            byoc_anomaly_rejection_rate_threshold=float(
                os.environ.get("EXO_BYOC_ANOMALY_REJECTION_RATE_THRESHOLD", "0.2")
            ),
            byoc_anomaly_reason_share_threshold=float(
                os.environ.get("EXO_BYOC_ANOMALY_REASON_SHARE_THRESHOLD", "0.6")
            ),
            byoc_anomaly_min_submit_attempts=int(
                os.environ.get("EXO_BYOC_ANOMALY_MIN_SUBMIT_ATTEMPTS", "5")
            ),
            byoc_anomaly_min_rejection_count=int(
                os.environ.get("EXO_BYOC_ANOMALY_MIN_REJECTION_COUNT", "3")
            ),
            byoc_fair_admission_enabled=_env_bool("EXO_BYOC_FAIR_ADMISSION_ENABLED", default=False),
            byoc_fair_admission_max_inflight_global=int(
                os.environ.get("EXO_BYOC_FAIR_ADMISSION_MAX_INFLIGHT_GLOBAL", "8")
            ),
            byoc_fair_admission_wait_timeout_ms=int(
                os.environ.get("EXO_BYOC_FAIR_ADMISSION_WAIT_TIMEOUT_MS", "1000")
            ),
            control_state_backend=_control_state_backend_from_env(),
            control_state_sqlite_db_path=_control_state_sqlite_db_path_from_env(),
            session_runtime_idle_ttl_seconds=_env_int_non_negative("EXO_SESSION_RUNTIME_IDLE_TTL_SECONDS", 0),
            session_runtime_max_cached_sessions=_env_int_non_negative(
                "EXO_SESSION_RUNTIME_MAX_CACHED_SESSIONS", 0
            ),
            run_control_max_terminal_records_per_tenant=_env_int_non_negative(
                "EXO_RUN_CONTROL_MAX_TERMINAL_RECORDS_PER_TENANT", 0
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
        policy=PolicySettings(
            ingress_latency_budget_ms=int(os.environ.get("EXO_INGRESS_LATENCY_BUDGET_MS", "75")),
            ingress_timeout_ms=int(os.environ.get("EXO_INGRESS_TIMEOUT_MS", "150")),
            ingress_timeout_fail_mode=os.environ.get("EXO_INGRESS_TIMEOUT_FAIL_MODE", "fail_closed"),
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
    return build_default_provider_registry(settings)


def create_app(title: str = "eXo-brain API", version: str = "0.1.0") -> FastAPI:
    """Create and return a configured FastAPI application instance."""
    exo_env = os.environ.get("EXO_ENV", "development")
    enable_openapi = _env_bool("EXO_ENABLE_OPENAPI", default=exo_env in ("development", "test"))
    cors_origins = _cors_origins_for_environment(exo_env)
    allow_credentials = False if cors_origins == ["*"] else True

    app = FastAPI(
        title=title,
        version=version,
        description=(
            "Provider-neutral AI orchestration platform. "
            "Deterministic tool execution, multi-tenant runtime isolation, "
            "SSE and WebSocket streaming."
        ),
        docs_url="/docs" if enable_openapi else None,
        redoc_url="/redoc" if enable_openapi else None,
        openapi_url="/openapi.json" if enable_openapi else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=allow_credentials,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["system"], summary="Platform liveness probe")
    async def health() -> dict:
        return {"status": "ok", "platform": "eXo-brain", "probe": "liveness"}

    @app.get("/ready", tags=["system"], summary="Readiness probe (persistence checks)", response_model=None)
    async def ready(request: Request) -> JSONResponse:
        snapshot = readiness_snapshot(request.app)
        status_code = 200 if bool(snapshot.get("ready")) else 503
        return JSONResponse(status_code=status_code, content=snapshot)

    if _env_bool("EXO_ENABLE_PROMETHEUS_METRICS", default=False):
        from src.api.routers.prometheus_metrics import router as prometheus_metrics_router

        app.include_router(prometheus_metrics_router)

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

    settings = _default_settings()
    validate_non_dev_secrets(settings)
    provider_registry = _default_provider_registry(settings)
    return bootstrap(app, provider_registry=provider_registry, settings=settings, persistence_backend="sqlite")
