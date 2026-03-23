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


def test_cors_origins_from_env_splits_and_trims(monkeypatch) -> None:
    monkeypatch.setenv("EXO_CORS_ORIGINS", " https://a.example ,https://b.example ")
    assert app_module._cors_origins_for_environment("production") == [
        "https://a.example",
        "https://b.example",
    ]


def test_cors_origins_empty_env_uses_wildcard_only_in_dev_like(monkeypatch) -> None:
    monkeypatch.delenv("EXO_CORS_ORIGINS", raising=False)
    assert app_module._cors_origins_for_environment("development") == ["*"]
    assert app_module._cors_origins_for_environment("production") == []


def test_prometheus_metrics_router_registered_when_env_enabled(monkeypatch, tmp_path) -> None:
    from fastapi.testclient import TestClient

    monkeypatch.setenv("EXO_ENABLE_PROMETHEUS_METRICS", "1")
    monkeypatch.setenv("EXO_DB_PATH", str(tmp_path / "exo.db"))
    app = app_module.create_app()
    with TestClient(app) as client:
        response = client.get("/metrics")
    assert response.status_code == 200
    assert "exo_build_info" in response.text
