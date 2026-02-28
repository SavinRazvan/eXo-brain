"""
File: settings.py
Path: src/config/settings.py
Role: Runtime and policy configuration contracts for provider-neutral execution.
Used By:
 - src/config/provider_registry.py
 - src/core/orchestrator.py
Depends On:
 - dataclasses
Notes:
 - Defaults are deterministic-first for safety-sensitive workloads.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from src.schemas.tool_io import RiskTier


class ModeSelectorStrategy(str, Enum):
    CAPABILITY_POLICY_DRIVEN = "capability_policy_driven"
    DETERMINISTIC_ONLY = "deterministic_only"
    PROVIDER_NATIVE_PREFERRED = "provider_native_preferred"


@dataclass(slots=True)
class RuntimeSettings:
    default_provider_id: str
    allowed_provider_ids: list[str]
    mode_selector: ModeSelectorStrategy = ModeSelectorStrategy.CAPABILITY_POLICY_DRIVEN
    fallback_provider_id: str | None = None
    require_provider_healthcheck_on_start: bool = True
    submit_tool_results_timeout_ms: int = 30000


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


@dataclass(slots=True)
class BackgroundRuntimeSettings:
    enabled: bool = False
    resume_enabled: bool = True
    checkpoint_store_backend: str = "in_memory"
    scheduler_fail_closed: bool = True


@dataclass(slots=True)
class AppSettings:
    schema_version: str
    environment: str
    runtime: RuntimeSettings
    policy: PolicySettings = field(default_factory=PolicySettings)
    observability: ObservabilitySettings = field(default_factory=ObservabilitySettings)
    limits: LimitsSettings = field(default_factory=LimitsSettings)
    background_runtime: BackgroundRuntimeSettings = field(default_factory=BackgroundRuntimeSettings)
