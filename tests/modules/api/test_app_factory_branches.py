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
from src.core.run_control_registry import RunControlRegistry, SQLiteRunControlRegistry
from src.tenancy.rate_limiter import SQLiteTenantRateLimiter, TenantRateLimiter


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


def test_control_state_backend_from_env(monkeypatch) -> None:
    monkeypatch.setenv("EXO_CONTROL_STATE_BACKEND", "sqlite")
    assert app_module._control_state_backend_from_env() == "sqlite"
    monkeypatch.setenv("EXO_CONTROL_STATE_BACKEND", "  SQLITE ")
    assert app_module._control_state_backend_from_env() == "sqlite"
    monkeypatch.setenv("EXO_CONTROL_STATE_BACKEND", "memory")
    assert app_module._control_state_backend_from_env() == "memory"
    monkeypatch.setenv("EXO_CONTROL_STATE_BACKEND", "postgres")
    assert app_module._control_state_backend_from_env() == "memory"


def test_env_int_non_negative(monkeypatch) -> None:
    monkeypatch.delenv("EXO_INT_TEST", raising=False)
    assert app_module._env_int_non_negative("EXO_INT_TEST", 7) == 7
    monkeypatch.setenv("EXO_INT_TEST", "")
    assert app_module._env_int_non_negative("EXO_INT_TEST", 7) == 7
    monkeypatch.setenv("EXO_INT_TEST", "42")
    assert app_module._env_int_non_negative("EXO_INT_TEST", 7) == 42
    monkeypatch.setenv("EXO_INT_TEST", "-3")
    assert app_module._env_int_non_negative("EXO_INT_TEST", 7) == 0
    monkeypatch.setenv("EXO_INT_TEST", "bad")
    assert app_module._env_int_non_negative("EXO_INT_TEST", 7) == 7


def test_control_state_sqlite_db_path_from_env(monkeypatch) -> None:
    monkeypatch.delenv("EXO_CONTROL_STATE_SQLITE_DB_PATH", raising=False)
    assert app_module._control_state_sqlite_db_path_from_env() == ".exo_data/exo_control_state.db"
    monkeypatch.setenv("EXO_CONTROL_STATE_SQLITE_DB_PATH", "  ")
    assert app_module._control_state_sqlite_db_path_from_env() == ".exo_data/exo_control_state.db"
    monkeypatch.setenv("EXO_CONTROL_STATE_SQLITE_DB_PATH", "/tmp/cs.db")
    assert app_module._control_state_sqlite_db_path_from_env() == "/tmp/cs.db"


def test_default_settings_reads_control_plane_scale_env(monkeypatch) -> None:
    monkeypatch.setenv("EXO_ENV", "test")
    monkeypatch.setenv("EXO_CONTROL_STATE_BACKEND", "sqlite")
    monkeypatch.setenv("EXO_CONTROL_STATE_SQLITE_DB_PATH", "/custom/control.db")
    monkeypatch.setenv("EXO_SESSION_RUNTIME_IDLE_TTL_SECONDS", "90")
    monkeypatch.setenv("EXO_SESSION_RUNTIME_MAX_CACHED_SESSIONS", "16")
    monkeypatch.setenv("EXO_TENANT_RUNTIME_MAX_CACHED_CONTEXTS", "32")
    monkeypatch.setenv("EXO_RUN_CONTROL_MAX_TERMINAL_RECORDS_PER_TENANT", "200")
    settings = app_module._default_settings()
    assert settings.runtime.control_state_backend == "sqlite"
    assert settings.runtime.control_state_sqlite_db_path == "/custom/control.db"
    assert settings.runtime.session_runtime_idle_ttl_seconds == 90
    assert settings.runtime.session_runtime_max_cached_sessions == 16
    assert settings.runtime.tenant_runtime_max_cached_contexts == 32
    assert settings.runtime.run_control_max_terminal_records_per_tenant == 200


def test_create_app_sqlite_control_state_from_env(monkeypatch, tmp_path) -> None:
    from fastapi.testclient import TestClient

    db = tmp_path / "exo.db"
    control_db = tmp_path / "control.db"
    monkeypatch.setenv("EXO_ENV", "test")
    monkeypatch.setenv("EXO_DB_PATH", str(db))
    monkeypatch.setenv("EXO_CONTROL_STATE_BACKEND", "sqlite")
    monkeypatch.setenv("EXO_CONTROL_STATE_SQLITE_DB_PATH", str(control_db))
    app = app_module.create_app()
    assert isinstance(app.state.run_control_registry, SQLiteRunControlRegistry)
    assert isinstance(app.state.turn_rate_limiter, SQLiteTenantRateLimiter)
    assert isinstance(app.state.tool_upload_rate_limiter, SQLiteTenantRateLimiter)
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200


def test_create_app_memory_control_state_when_env_default(monkeypatch, tmp_path) -> None:
    db = tmp_path / "exo.db"
    monkeypatch.setenv("EXO_ENV", "test")
    monkeypatch.setenv("EXO_DB_PATH", str(db))
    monkeypatch.delenv("EXO_CONTROL_STATE_BACKEND", raising=False)
    app = app_module.create_app()
    assert isinstance(app.state.run_control_registry, RunControlRegistry)
    assert isinstance(app.state.turn_rate_limiter, TenantRateLimiter)
    assert isinstance(app.state.tool_upload_rate_limiter, TenantRateLimiter)
