"""
File: test_settings.py
Path: tests/modules/config/test_settings.py
Role: Unit tests for config dataclasses and enums in `src/config/settings.py` (FIND-008).
Used By:
 - pytest
Depends On:
 - src/config/settings.py
 - src/schemas/tool_io.py
"""

from __future__ import annotations

from src.config.settings import (
    AppSettings,
    AuthSettings,
    BackgroundRuntimeSettings,
    DeploymentProfile,
    DeterministicPolicySettings,
    LimitsSettings,
    ModeSelectorStrategy,
    ObservabilitySettings,
    PolicySettings,
    RuntimeSettings,
)
from src.schemas.tool_io import RiskTier


def test_mode_selector_strategy_string_enum_values() -> None:
    assert ModeSelectorStrategy.CAPABILITY_POLICY_DRIVEN == "capability_policy_driven"
    assert ModeSelectorStrategy.DETERMINISTIC_ONLY == "deterministic_only"
    assert ModeSelectorStrategy.PROVIDER_NATIVE_PREFERRED == "provider_native_preferred"


def test_deployment_profile_string_enum_values() -> None:
    assert DeploymentProfile.MANAGED_CLOUD == "managed_cloud"
    assert DeploymentProfile.SELF_HOSTED == "self_hosted"
    assert DeploymentProfile.HYBRID == "hybrid"


def test_deterministic_policy_settings_default_risk_tiers() -> None:
    det = DeterministicPolicySettings()
    assert det.state_changing is True
    assert det.risk_tiers == [RiskTier.HIGH, RiskTier.CRITICAL]


def test_policy_settings_nested_defaults_are_fresh() -> None:
    first = PolicySettings()
    second = PolicySettings()
    assert first.deterministic_required_for is not second.deterministic_required_for
    assert first.deterministic_required_for.risk_tiers == second.deterministic_required_for.risk_tiers


def test_runtime_settings_distinct_mutable_defaults() -> None:
    left = RuntimeSettings(default_provider_id="a", allowed_provider_ids=["a"])
    right = RuntimeSettings(default_provider_id="b", allowed_provider_ids=["b"])
    assert left.byoc_budget_partition_limits_microunits is not right.byoc_budget_partition_limits_microunits
    assert left.byoc_budget_partition_limits_microunits == {}


def test_limits_settings_distinct_mutable_defaults() -> None:
    left = LimitsSettings()
    right = LimitsSettings()
    assert left.audit_bundle_signing_secrets_by_version is not right.audit_bundle_signing_secrets_by_version
    assert left.allowed_tool_dependency_prefixes is not right.allowed_tool_dependency_prefixes


def test_auth_settings_jwt_and_cross_tenant_defaults() -> None:
    auth = AuthSettings()
    assert auth.jwt_secret == ""
    assert auth.jwks_url == ""
    assert auth.algorithm == "HS256"
    assert auth.allow_cross_tenant_admin is False
    assert auth.cross_tenant_admin_roles == ["super_admin"]


def test_app_settings_composes_expected_sub_settings() -> None:
    settings = AppSettings(
        schema_version="1.0",
        environment="test",
        runtime=RuntimeSettings(
            default_provider_id="p1",
            allowed_provider_ids=["p1"],
            require_provider_healthcheck_on_start=False,
        ),
    )
    assert isinstance(settings.policy, PolicySettings)
    assert isinstance(settings.limits, LimitsSettings)
    assert isinstance(settings.auth, AuthSettings)
    assert isinstance(settings.observability, ObservabilitySettings)
    assert isinstance(settings.background_runtime, BackgroundRuntimeSettings)
    assert settings.deployment_profile == DeploymentProfile.MANAGED_CLOUD
