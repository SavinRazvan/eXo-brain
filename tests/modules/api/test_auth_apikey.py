"""
File: test_auth_apikey.py
Path: tests/modules/api/test_auth_apikey.py
Role: Acceptance tests for Slice 1 Step A — API-key authentication and key management.
Used By:
 - pytest
Depends On:
 - src/api/routers/admin_keys.py
 - src/api/middleware/auth.py
 - src/persistence/adapters/sqlite.py
Notes:
 - Uses a SQLite-backed app (temp file) so admin key CRUD + auth can be round-tripped.
 - build_test_app() (memory backend) has no api_key_store — admin endpoints return 503.
 - X-Identity is used to bootstrap key creation (test environment allows it).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.bootstrap import build_test_app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _x_identity(tenant_id: str = "t1", subject: str = "admin@test") -> dict:
    return {
        "X-Identity": json.dumps({
            "subject": subject,
            "roles": ["admin"],
            "tenant_id": tenant_id,
            "token_validation_state": "valid",
        })
    }


def _build_sqlite_test_app(db_path: Path):
    """Build a test app backed by a real SQLite store (so API keys persist in-process)."""
    import os
    from src.api.app import create_app
    from src.api.bootstrap import bootstrap
    from src.config.provider_registry import (
        AuthConfig, EndpointApiType, EndpointConfig, ModelDefaults,
        ProviderProfile, ProviderRecord, ProviderRegistry,
    )
    from src.config.settings import AppSettings, RuntimeSettings
    from src.runtime.openai_agents_runtime import OpenAIAgentsRuntimeAdapter

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
    record = ProviderRecord(
        provider_id="openai-test",
        display_name="Test OpenAI",
        adapter_class="OpenAIAgentsRuntimeAdapter",
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
    provider_registry = ProviderRegistry(
        settings=settings,
        providers=[record],
        adapters={"openai-test": adapter},
    )
    app = create_app()
    old = os.environ.get("EXO_DB_PATH")
    os.environ["EXO_DB_PATH"] = str(db_path)
    try:
        bootstrap(app, provider_registry, settings, persistence_backend="sqlite")
    finally:
        if old is None:
            os.environ.pop("EXO_DB_PATH", None)
        else:
            os.environ["EXO_DB_PATH"] = old
    return app


# ---------------------------------------------------------------------------
# Tests — admin key CRUD
# ---------------------------------------------------------------------------


def test_create_api_key_returns_plaintext_once(tmp_path: Path) -> None:
    """POST /admin/keys creates a key and returns the plaintext value."""
    app = _build_sqlite_test_app(tmp_path / "exo.db")
    with TestClient(app) as client:
        resp = client.post(
            "/admin/keys",
            json={"tenant_id": "t1", "subject": "svc@example.com", "roles": ["user"], "description": "test key"},
            headers=_x_identity(),
        )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["key"].startswith("exo_")
    assert len(data["key"]) > 10
    assert data["key_id"]
    assert data["tenant_id"] == "t1"
    assert data["subject"] == "svc@example.com"
    assert data["roles"] == ["user"]


def test_list_api_keys(tmp_path: Path) -> None:
    """GET /admin/keys lists created keys (no plaintext keys in response)."""
    app = _build_sqlite_test_app(tmp_path / "exo.db")
    with TestClient(app) as client:
        client.post(
            "/admin/keys",
            json={"tenant_id": "t1", "subject": "a@example.com", "roles": []},
            headers=_x_identity(),
        )
        client.post(
            "/admin/keys",
            json={"tenant_id": "t1", "subject": "b@example.com", "roles": []},
            headers=_x_identity(),
        )
        resp = client.get("/admin/keys", headers=_x_identity())
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    for key_info in data["keys"]:
        assert "key" not in key_info
        assert "key_hash" not in key_info


def test_list_api_keys_filtered_by_tenant(tmp_path: Path) -> None:
    """GET /admin/keys?tenant_id=t1 returns only t1's keys."""
    app = _build_sqlite_test_app(tmp_path / "exo.db")
    with TestClient(app) as client:
        client.post(
            "/admin/keys",
            json={"tenant_id": "t1", "subject": "a@t1.com", "roles": []},
            headers=_x_identity("t1"),
        )
        client.post(
            "/admin/keys",
            json={"tenant_id": "t2", "subject": "b@t2.com", "roles": []},
            headers=_x_identity("t2"),
        )
        resp = client.get("/admin/keys?tenant_id=t1", headers=_x_identity())
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["keys"][0]["tenant_id"] == "t1"


def test_delete_api_key(tmp_path: Path) -> None:
    """DELETE /admin/keys/{key_id} removes the key; subsequent auth with it returns 401."""
    app = _build_sqlite_test_app(tmp_path / "exo.db")
    with TestClient(app) as client:
        create_resp = client.post(
            "/admin/keys",
            json={"tenant_id": "t1", "subject": "svc@t1.com", "roles": ["user"]},
            headers=_x_identity(),
        )
        raw_key = create_resp.json()["key"]
        key_id = create_resp.json()["key_id"]

        del_resp = client.delete(f"/admin/keys/{key_id}", headers=_x_identity())
        assert del_resp.status_code == 204

        auth_resp = client.get("/admin/keys", headers={"Authorization": f"Bearer {raw_key}"})
        assert auth_resp.status_code == 401


def test_delete_nonexistent_key_returns_404(tmp_path: Path) -> None:
    app = _build_sqlite_test_app(tmp_path / "exo.db")
    with TestClient(app) as client:
        resp = client.delete("/admin/keys/ghost-key-id", headers=_x_identity())
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests — authentication with API key
# ---------------------------------------------------------------------------


def test_api_key_authenticates_successfully(tmp_path: Path) -> None:
    """A valid API key in Authorization: Bearer authenticates successfully."""
    app = _build_sqlite_test_app(tmp_path / "exo.db")
    with TestClient(app) as client:
        create_resp = client.post(
            "/admin/keys",
            json={"tenant_id": "t1", "subject": "svc@t1.com", "roles": ["user"]},
            headers=_x_identity(),
        )
        raw_key = create_resp.json()["key"]

        resp = client.get(
            "/admin/keys",
            headers={"Authorization": f"Bearer {raw_key}"},
        )
    assert resp.status_code == 200


def test_api_key_via_x_api_key_header(tmp_path: Path) -> None:
    """A valid API key in X-API-Key header authenticates successfully."""
    app = _build_sqlite_test_app(tmp_path / "exo.db")
    with TestClient(app) as client:
        create_resp = client.post(
            "/admin/keys",
            json={"tenant_id": "t1", "subject": "svc@t1.com", "roles": ["user"]},
            headers=_x_identity(),
        )
        raw_key = create_resp.json()["key"]

        resp = client.get(
            "/admin/keys",
            headers={"X-API-Key": raw_key},
        )
    assert resp.status_code == 200


def test_unknown_api_key_returns_401(tmp_path: Path) -> None:
    """An unknown/random API key returns 401."""
    app = _build_sqlite_test_app(tmp_path / "exo.db")
    with TestClient(app) as client:
        resp = client.get(
            "/admin/keys",
            headers={"Authorization": "Bearer exo_unknownkeyvalue"},
        )
    assert resp.status_code == 401


def test_x_identity_blocked_in_production_environment(tmp_path: Path) -> None:
    """X-Identity is rejected when environment=production."""
    import os
    from src.api.app import create_app
    from src.api.bootstrap import bootstrap
    from src.config.provider_registry import (
        AuthConfig, EndpointApiType, EndpointConfig, ModelDefaults,
        ProviderProfile, ProviderRecord, ProviderRegistry,
    )
    from src.config.settings import AppSettings, RuntimeSettings
    from src.runtime.openai_agents_runtime import OpenAIAgentsRuntimeAdapter

    settings = AppSettings(
        schema_version="1.0",
        environment="production",
        runtime=RuntimeSettings(
            default_provider_id="openai-test",
            allowed_provider_ids=["openai-test"],
            require_provider_healthcheck_on_start=False,
        ),
    )
    adapter = OpenAIAgentsRuntimeAdapter(provider_id="openai-test")
    record = ProviderRecord(
        provider_id="openai-test",
        display_name="Test OpenAI",
        adapter_class="OpenAIAgentsRuntimeAdapter",
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
    provider_registry = ProviderRegistry(
        settings=settings,
        providers=[record],
        adapters={"openai-test": adapter},
    )
    app = create_app()
    old = os.environ.get("EXO_DB_PATH")
    db_path = tmp_path / "prod.db"
    os.environ["EXO_DB_PATH"] = str(db_path)
    try:
        bootstrap(app, provider_registry, settings, persistence_backend="sqlite")
    finally:
        if old is None:
            os.environ.pop("EXO_DB_PATH", None)
        else:
            os.environ["EXO_DB_PATH"] = old

    with TestClient(app) as client:
        resp = client.get(
            "/admin/keys",
            headers={"X-Identity": json.dumps({"subject": "alice", "tenant_id": "t1",
                                                "token_validation_state": "valid"})},
        )
    assert resp.status_code == 401


def test_x_identity_allowed_in_test_environment() -> None:
    """X-Identity is accepted when environment=test (build_test_app default)."""
    app = build_test_app()
    with TestClient(app) as client:
        resp = client.get(
            "/health",
            headers={"X-Identity": json.dumps({"subject": "alice", "tenant_id": "t1",
                                                "token_validation_state": "valid"})},
        )
    assert resp.status_code == 200


def test_admin_keys_requires_auth() -> None:
    """GET /admin/keys returns 401 when no auth provided (memory backend, no store)."""
    app = build_test_app()
    with TestClient(app) as client:
        resp = client.get("/admin/keys")
    assert resp.status_code == 401


def test_admin_keys_returns_503_without_store() -> None:
    """GET /admin/keys returns 503 when api_key_store is None (memory backend)."""
    app = build_test_app()
    with TestClient(app) as client:
        resp = client.get("/admin/keys", headers=_x_identity())
    assert resp.status_code == 503
