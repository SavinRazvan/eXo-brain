"""
File: test_slice_provider_registration.py
Path: tests/modules/api/test_slice_provider_registration.py
Role: Acceptance tests for Slice 2 — Dynamic Provider Registration API.
Used By:
 - pytest
Depends On:
 - src/api/routers/providers.py
 - src/runtime/adapter_factory.py
 - src/persistence/adapters/sqlite.py
Notes:
 - Uses SQLite-backed app so provider persistence and hydration can be tested.
 - OpenAIAgentsRuntimeAdapter is used as the dynamic adapter (requires OPENAI_API_KEY or stub).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _x_identity() -> dict:
    return {
        "X-Identity": json.dumps({
            "subject": "admin@test",
            "roles": ["admin"],
            "tenant_id": "t1",
            "token_validation_state": "valid",
        })
    }


def _x_identity_with_roles(*roles: str) -> dict:
    payload = {
        "subject": "admin@test",
        "roles": [role for role in roles],
        "tenant_id": "t1",
        "token_validation_state": "valid",
    }
    return {"X-Identity": json.dumps(payload)}


def _build_sqlite_provider_app(db_path: Path, *, enable_graceful_drain: bool = False):
    """Build a test app with SQLite persistence and one bootstrap provider."""
    import os
    from src.api.app import create_app
    from src.api.bootstrap import bootstrap
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
    from src.runtime.adapter_factory import OPENAI_ADAPTER_CANONICAL_CLASS_REF
    from src.runtime.openai_agents_runtime import OpenAIAgentsRuntimeAdapter

    settings = AppSettings(
        schema_version="1.0",
        environment="test",
        runtime=RuntimeSettings(
            default_provider_id="openai-test",
            allowed_provider_ids=["openai-test"],
            require_provider_healthcheck_on_start=False,
            enable_provider_delete_graceful_drain=enable_graceful_drain,
        ),
    )
    adapter = OpenAIAgentsRuntimeAdapter(provider_id="openai-test")
    record = ProviderRecord(
        provider_id="openai-test",
        display_name="Test OpenAI",
        adapter_class=OPENAI_ADAPTER_CANONICAL_CLASS_REF,
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


def test_post_providers_creates_dynamic_provider(tmp_path: Path) -> None:
    """POST /providers with valid adapter_class_ref returns 201 and provider is listed."""
    import asyncio

    from src.runtime.adapter_factory import OPENAI_ADAPTER_CANONICAL_CLASS_REF

    app = _build_sqlite_provider_app(tmp_path / "exo.db")
    with TestClient(app) as client:
        resp = client.post(
            "/providers",
            json={
                "provider_id": "dynamic-openai",
                "display_name": "Dynamic OpenAI",
                "adapter_class_ref": OPENAI_ADAPTER_CANONICAL_CLASS_REF,
                "api_key_env_var": "OPENAI_API_KEY",
                "base_url": "https://api.openai.com",
                "model": "gpt-4o-mini",
                "profile": "managed_vendor",
            },
            headers=_x_identity(),
        )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["provider_id"] == "dynamic-openai"
    assert data["display_name"] == "Dynamic OpenAI"
    assert data["enabled"] is True

    with TestClient(app) as client:
        list_resp = client.get("/providers", headers=_x_identity())
    assert list_resp.status_code == 200
    providers = list_resp.json()["providers"]
    ids = [p["provider_id"] for p in providers]
    assert "openai-test" in ids
    assert "dynamic-openai" in ids
    stored = asyncio.run(app.state.provider_store.get_provider("dynamic-openai"))
    assert stored is not None
    assert stored.adapter_class == OPENAI_ADAPTER_CANONICAL_CLASS_REF


def test_post_providers_legacy_alias_is_canonicalized(tmp_path: Path) -> None:
    import asyncio

    from src.runtime.adapter_factory import OPENAI_ADAPTER_CANONICAL_CLASS_REF

    app = _build_sqlite_provider_app(tmp_path / "exo.db")
    with TestClient(app) as client:
        resp = client.post(
            "/providers",
            json={
                "provider_id": "legacy-alias-provider",
                "display_name": "Legacy Alias",
                "adapter_class_ref": "OpenAIAgentsRuntimeAdapter",
            },
            headers=_x_identity(),
        )
    assert resp.status_code == 201, resp.text
    stored = asyncio.run(app.state.provider_store.get_provider("legacy-alias-provider"))
    assert stored is not None
    assert stored.adapter_class == OPENAI_ADAPTER_CANONICAL_CLASS_REF


def test_post_providers_duplicate_returns_409(tmp_path: Path) -> None:
    """POST /providers with existing provider_id returns 409."""
    app = _build_sqlite_provider_app(tmp_path / "exo.db")
    with TestClient(app) as client:
        client.post(
            "/providers",
            json={
                "provider_id": "dup-provider",
                "display_name": "First",
                "adapter_class_ref": "src.runtime.openai_agents_runtime.OpenAIAgentsRuntimeAdapter",
            },
            headers=_x_identity(),
        )
        resp = client.post(
            "/providers",
            json={
                "provider_id": "dup-provider",
                "display_name": "Second",
                "adapter_class_ref": "src.runtime.openai_agents_runtime.OpenAIAgentsRuntimeAdapter",
            },
            headers=_x_identity(),
        )
    assert resp.status_code == 409


def test_post_providers_invalid_adapter_returns_422(tmp_path: Path) -> None:
    """POST /providers with invalid adapter_class_ref returns 422."""
    app = _build_sqlite_provider_app(tmp_path / "exo.db")
    with TestClient(app) as client:
        resp = client.post(
            "/providers",
            json={
                "provider_id": "bad-adapter",
                "display_name": "Bad",
                "adapter_class_ref": "nonexistent.module.NoSuchAdapter",
            },
            headers=_x_identity(),
        )
    assert resp.status_code == 422


def test_delete_providers_succeeds(tmp_path: Path) -> None:
    """DELETE /providers/{id} removes the provider when no active sessions."""
    app = _build_sqlite_provider_app(tmp_path / "exo.db")
    with TestClient(app) as client:
        client.post(
            "/providers",
            json={
                "provider_id": "to-delete",
                "display_name": "To Delete",
                "adapter_class_ref": "src.runtime.openai_agents_runtime.OpenAIAgentsRuntimeAdapter",
            },
            headers=_x_identity(),
        )
        del_resp = client.delete("/providers/to-delete", headers=_x_identity())
    assert del_resp.status_code == 204

    with TestClient(app) as client:
        list_resp = client.get("/providers", headers=_x_identity())
    ids = [p["provider_id"] for p in list_resp.json()["providers"]]
    assert "to-delete" not in ids


def test_delete_providers_with_active_sessions_returns_409(tmp_path: Path) -> None:
    """DELETE /providers/{id} returns 409 when active sessions use the provider."""
    app = _build_sqlite_provider_app(tmp_path / "exo.db")
    with TestClient(app) as client:
        client.post(
            "/providers",
            json={
                "provider_id": "busy-provider",
                "display_name": "Busy",
                "adapter_class_ref": "src.runtime.openai_agents_runtime.OpenAIAgentsRuntimeAdapter",
            },
            headers=_x_identity(),
        )
        client.post(
            "/tenants/t1/agents",
            json={
                "agent_id": "ag1",
                "role": "assistant",
                "capability_tags": [],
                "instructions": "Help",
            },
            headers=_x_identity(),
        )
        client.post(
            "/tenants/t1/sessions",
            json={
                "agent_id": "ag1",
                "provider_id": "busy-provider",
                "correlation_id": "corr1",
            },
            headers=_x_identity(),
        )
        del_resp = client.delete("/providers/busy-provider", headers=_x_identity())
    assert del_resp.status_code == 409
    assert "active session" in del_resp.json()["detail"]


def test_delete_providers_nonexistent_returns_404(tmp_path: Path) -> None:
    """DELETE /providers/{id} for unknown provider returns 404."""
    app = _build_sqlite_provider_app(tmp_path / "exo.db")
    with TestClient(app) as client:
        resp = client.delete("/providers/ghost-provider", headers=_x_identity())
    assert resp.status_code == 404


def test_provider_survives_restart(tmp_path: Path) -> None:
    """Dynamically registered provider is hydrated after simulated restart."""
    db_path = tmp_path / "exo.db"
    app1 = _build_sqlite_provider_app(db_path)
    with TestClient(app1) as client:
        client.post(
            "/providers",
            json={
                "provider_id": "survives-restart",
                "display_name": "Survives",
                "adapter_class_ref": "src.runtime.openai_agents_runtime.OpenAIAgentsRuntimeAdapter",
            },
            headers=_x_identity(),
        )

    app2 = _build_sqlite_provider_app(db_path)
    with TestClient(app2) as client:
        list_resp = client.get("/providers", headers=_x_identity())
    ids = [p["provider_id"] for p in list_resp.json()["providers"]]
    assert "survives-restart" in ids


def test_provider_store_unavailable_returns_503() -> None:
    """POST/DELETE /providers returns 503 when provider_store is None (memory backend)."""
    from src.api.bootstrap import build_test_app

    app = build_test_app()
    with TestClient(app) as client:
        post_resp = client.post(
            "/providers",
            json={
                "provider_id": "x",
                "display_name": "X",
                "adapter_class_ref": "src.runtime.openai_agents_runtime.OpenAIAgentsRuntimeAdapter",
            },
            headers=_x_identity(),
        )
        del_resp = client.delete("/providers/openai-test", headers=_x_identity())
    assert post_resp.status_code == 503
    assert del_resp.status_code == 503


def test_delete_provider_force_drain_rejected_when_feature_disabled(tmp_path: Path) -> None:
    app = _build_sqlite_provider_app(tmp_path / "exo.db", enable_graceful_drain=False)
    with TestClient(app) as client:
        client.post(
            "/providers",
            json={
                "provider_id": "busy-provider",
                "display_name": "Busy",
                "adapter_class_ref": "src.runtime.openai_agents_runtime.OpenAIAgentsRuntimeAdapter",
            },
            headers=_x_identity(),
        )
        client.post(
            "/tenants/t1/agents",
            json={
                "agent_id": "ag1",
                "role": "assistant",
                "capability_tags": [],
                "instructions": "Help",
            },
            headers=_x_identity(),
        )
        client.post(
            "/tenants/t1/sessions",
            json={
                "agent_id": "ag1",
                "provider_id": "busy-provider",
                "correlation_id": "corr1",
            },
            headers=_x_identity(),
        )
        del_resp = client.delete("/providers/busy-provider?force_drain=true", headers=_x_identity())
    assert del_resp.status_code == 403
    assert "Graceful drain is disabled" in del_resp.json()["detail"]


def test_delete_provider_force_drain_succeeds_when_feature_enabled(tmp_path: Path) -> None:
    import asyncio

    app = _build_sqlite_provider_app(tmp_path / "exo.db", enable_graceful_drain=True)
    with TestClient(app) as client:
        client.post(
            "/providers",
            json={
                "provider_id": "busy-provider",
                "display_name": "Busy",
                "adapter_class_ref": "src.runtime.openai_agents_runtime.OpenAIAgentsRuntimeAdapter",
            },
            headers=_x_identity(),
        )
        client.post(
            "/tenants/t1/agents",
            json={
                "agent_id": "ag1",
                "role": "assistant",
                "capability_tags": [],
                "instructions": "Help",
            },
            headers=_x_identity(),
        )
        client.post(
            "/tenants/t1/sessions",
            json={
                "agent_id": "ag1",
                "provider_id": "busy-provider",
                "correlation_id": "corr1",
            },
            headers=_x_identity(),
        )
        del_resp = client.delete(
            "/providers/busy-provider?force_drain=true",
            headers=_x_identity_with_roles("admin"),
        )
        assert del_resp.status_code == 204
        list_resp = client.get("/providers", headers=_x_identity())
        ids = [p["provider_id"] for p in list_resp.json()["providers"]]
        assert "busy-provider" not in ids

    remaining = asyncio.run(app.state.session_store.count_active_sessions_by_provider("busy-provider"))
    assert remaining == 0
