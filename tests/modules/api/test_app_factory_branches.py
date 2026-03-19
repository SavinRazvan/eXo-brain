"""
File: test_app_factory_branches.py
Path: tests/modules/api/test_app_factory_branches.py
Role: Branch-focused tests for app factory environment parsing helpers.
Used By:
 - pytest
Depends On:
 - src/api/app.py
Notes:
 - Targets JSON parsing and env-boolean edge branches in _default_settings.
"""

from __future__ import annotations

from src.api import app as app_module


def test_env_bool_true_when_enabled_token(monkeypatch) -> None:
    monkeypatch.setenv("EXO_FLAG_TEST", "YES")
    assert app_module._env_bool("EXO_FLAG_TEST", default=False) is True


def test_default_settings_parses_signing_and_budget_maps(monkeypatch) -> None:
    monkeypatch.setenv("EXO_AUDIT_BUNDLE_SIGNING_SECRETS_BY_VERSION", '{"v1":"secret","":"skip","v2":"  "}')
    monkeypatch.setenv(
        "EXO_BYOC_BUDGET_PARTITION_LIMITS_MICROUNITS_JSON",
        '{"provider:openai-test":"15","":"9","tool:bad":"not-int"}',
    )
    settings = app_module._default_settings()
    assert settings.limits.audit_bundle_signing_secrets_by_version == {"v1": "secret"}
    assert settings.runtime.byoc_budget_partition_limits_microunits == {"provider:openai-test": 15}


def test_default_settings_invalid_json_falls_back_to_empty_maps(monkeypatch) -> None:
    monkeypatch.setenv("EXO_AUDIT_BUNDLE_SIGNING_SECRETS_BY_VERSION", "{not-json")
    monkeypatch.setenv("EXO_BYOC_BUDGET_PARTITION_LIMITS_MICROUNITS_JSON", "{also-not-json")
    settings = app_module._default_settings()
    assert settings.limits.audit_bundle_signing_secrets_by_version == {}
    assert settings.runtime.byoc_budget_partition_limits_microunits == {}
