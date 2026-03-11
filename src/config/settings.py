"""
File: settings.py
Path: src/config/settings.py
Role: Runtime, auth, and policy configuration contracts for provider-neutral execution.
Used By:
 - src/config/provider_registry.py
 - src/core/orchestrator.py
 - src/api/middleware/auth.py
Depends On:
 - dataclasses
Notes:
 - Defaults are deterministic-first for safety-sensitive workloads.
 - AuthSettings.jwt_secret / jwks_url control JWT verification.
 - X-Identity plain-JSON is allowed only when AppSettings.environment is 'test' or 'development'.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from src.schemas.tool_io import RiskTier


class ModeSelectorStrategy(str, Enum):
    CAPABILITY_POLICY_DRIVEN = "capability_policy_driven"
    DETERMINISTIC_ONLY = "deterministic_only"
    PROVIDER_NATIVE_PREFERRED = "provider_native_preferred"


class DeploymentProfile(str, Enum):
    MANAGED_CLOUD = "managed_cloud"
    SELF_HOSTED = "self_hosted"
    HYBRID = "hybrid"


@dataclass(slots=True)
class RuntimeSettings:
    default_provider_id: str
    allowed_provider_ids: list[str]
    mode_selector: ModeSelectorStrategy = ModeSelectorStrategy.CAPABILITY_POLICY_DRIVEN
    fallback_provider_id: str | None = None
    require_provider_healthcheck_on_start: bool = True
    submit_tool_results_timeout_ms: int = 30000
    enable_hosted_tool_runtime: bool = False
    enable_hosted_tool_process_isolation: bool = False
    enable_byoc_tool_runtime: bool = False
    enable_provider_delete_graceful_drain: bool = False
    byoc_worker_jwt_secret: str = "exo-byoc-dev-secret"
    byoc_worker_token_ttl_seconds: int = 300
    byoc_store_backend: str = "memory"
    byoc_sqlite_db_path: str = ".exo_data/exo.db"
    byoc_lease_ttl_seconds: int = 30
    byoc_replay_ttl_seconds: int = 300
    byoc_cleanup_interval_seconds: int = 30
    byoc_completed_ttl_seconds: int = 3600
    byoc_cancelled_ttl_seconds: int = 3600
    byoc_result_ttl_seconds: int = 3600
    byoc_idempotency_ttl_seconds: int = 3600
    byoc_max_completed_records: int = 2000
    byoc_max_cancelled_records: int = 2000
    byoc_max_result_records: int = 2000
    byoc_max_claim_attempts_before_dlq: int = 3
    byoc_result_conflict_strategy: str = "first_write_wins"
    byoc_cost_limit_microunits_per_tenant: int = 1_000_000
    byoc_enforce_cost_limit: bool = False
    byoc_enable_cost_window_policy: bool = False
    byoc_cost_window_seconds: int = 3600
    byoc_cost_success_microunits: int = 100
    byoc_cost_error_microunits: int = 40
    byoc_cost_timeout_microunits: int = 60
    byoc_cost_cancelled_microunits: int = 20
    byoc_budget_partition_scope: str = "tenant"
    byoc_budget_partition_limits_microunits: dict[str, int] = field(default_factory=dict)
    byoc_anomaly_detection_enabled: bool = True
    byoc_anomaly_cost_utilization_threshold: float = 0.9
    byoc_anomaly_rejection_rate_threshold: float = 0.2
    byoc_anomaly_reason_share_threshold: float = 0.6
    byoc_anomaly_min_submit_attempts: int = 5
    byoc_anomaly_min_rejection_count: int = 3
    byoc_fair_admission_enabled: bool = False
    byoc_fair_admission_max_inflight_global: int = 8
    byoc_fair_admission_wait_timeout_ms: int = 1000
    byoc_fair_admission_backend: str = "memory"
    byoc_non_blocking_execute: bool = False
    control_state_backend: str = "memory"
    control_state_sqlite_db_path: str = ".exo_data/exo_control_state.db"


@dataclass(slots=True)
class DeterministicPolicySettings:
    state_changing: bool = True
    risk_tiers: list[RiskTier] = field(default_factory=lambda: [RiskTier.HIGH, RiskTier.CRITICAL])


@dataclass(slots=True)
class PolicySettings:
    deterministic_required_for: DeterministicPolicySettings = field(default_factory=DeterministicPolicySettings)
    allow_provider_native_for_read_only_low_risk: bool = True
    block_on_capability_unknown: bool = True
    escalation_channel: str = "security-review"


@dataclass(slots=True)
class ObservabilitySettings:
    require_correlation_ids: bool = True
    log_provider_decisions: bool = True
    emit_mode_selection_reasons: bool = True


@dataclass(slots=True)
class LimitsSettings:
    max_parallel_jobs: int = 20
    # Legacy field name retained for compatibility; "risky" means state-changing/high-impact operations.
    max_concurrent_risky_tools_per_session: int = 1
    default_tool_timeout_ms: int = 30000
    max_active_runs_per_tenant: int = 50
    max_turn_requests_per_minute_per_tenant: int = 120
    max_tool_uploads_per_minute_per_tenant: int = 30
    max_tool_upload_size_bytes: int = 5_000_000
    tool_artifact_directory: str = ".exo_data/tool_artifacts"
    tool_artifact_signing_secret: str = "exo-tool-artifact-dev-secret"
    allowed_tool_dependency_prefixes: list[str] = field(default_factory=list)
    max_audit_records_per_tenant: int = 10_000
    max_audit_export_records: int = 2_000
    audit_export_directory: str = ".exo_data/audit_exports"
    audit_bundle_signing_secret: str = "exo-audit-dev-secret"
    audit_bundle_signing_active_version: str = "v1"
    audit_bundle_signing_secrets_by_version: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class BackgroundRuntimeSettings:
    enabled: bool = False
    resume_enabled: bool = True
    checkpoint_store_backend: str = "in_memory"
    scheduler_fail_closed: bool = True


@dataclass(slots=True)
class AuthSettings:
    """Authentication configuration for JWT Bearer and API-key modes.

    jwt_secret:  symmetric secret for HS256/HS512 token verification.
    jwks_url:    JWKS endpoint URL for RS256/RS384/RS512 (takes precedence over jwt_secret).
    algorithm:   default JWT algorithm; must match the token header.
    """

    jwt_secret: str = ""
    jwks_url: str = ""
    algorithm: str = "HS256"
    # Disabled by default: tenant-scoped APIs enforce identity.tenant_id == path tenant_id.
    allow_cross_tenant_admin: bool = False
    cross_tenant_admin_roles: list[str] = field(default_factory=lambda: ["super_admin"])


@dataclass(slots=True)
class AppSettings:
    schema_version: str
    environment: str
    runtime: RuntimeSettings
    deployment_profile: DeploymentProfile = DeploymentProfile.MANAGED_CLOUD
    policy: PolicySettings = field(default_factory=PolicySettings)
    observability: ObservabilitySettings = field(default_factory=ObservabilitySettings)
    limits: LimitsSettings = field(default_factory=LimitsSettings)
    background_runtime: BackgroundRuntimeSettings = field(default_factory=BackgroundRuntimeSettings)
    auth: AuthSettings = field(default_factory=AuthSettings)
