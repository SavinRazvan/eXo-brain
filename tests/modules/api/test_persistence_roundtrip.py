"""
File: test_persistence_roundtrip.py
Path: tests/modules/api/test_persistence_roundtrip.py
Role: Acceptance tests for Slice 0 — persistent tool/agent registry survives server restart.
Used By:
 - pytest
Depends On:
 - src/api/bootstrap.py
 - src/api/startup.py
 - src/persistence/adapters/sqlite.py
 - src/persistence/contracts.py
Notes:
 - Uses a temporary SQLite file on disk to simulate restart (two separate app instances).
 - Hydration is tested by calling hydrate_tenant_registries() directly after the second
   app is bootstrapped, before any HTTP requests.
 - build_test_app() (memory backend) is unaffected by these tests.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.bootstrap import bootstrap, build_test_app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _headers(tenant_id: str = "t1") -> dict:
    payload = {
        "subject": "user@test.com",
        "roles": ["user"],
        "tenant_id": tenant_id,
        "token_validation_state": "valid",
    }
    return {"X-Identity": json.dumps(payload)}


def _build_sqlite_app(db_path: Path) -> FastAPI:
    """Bootstrap a fully configured app backed by the given SQLite file."""
    from src.api.app import create_app
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
    old_env = os.environ.get("EXO_DB_PATH")
    os.environ["EXO_DB_PATH"] = str(db_path)
    try:
        bootstrap(app, provider_registry, settings, persistence_backend="sqlite")
    finally:
        if old_env is None:
            os.environ.pop("EXO_DB_PATH", None)
        else:
            os.environ["EXO_DB_PATH"] = old_env
    return app


# ---------------------------------------------------------------------------
# Tests — tool persistence roundtrip
# ---------------------------------------------------------------------------


def test_tool_survives_restart(tmp_path: Path) -> None:
    """Register a tool, simulate restart, verify it is hydrated into the new app."""
    db_path = tmp_path / "exo.db"

    # -- First app instance: register tool
    with TestClient(_build_sqlite_app(db_path), raise_server_exceptions=True) as client1:
        resp = client1.post(
            "/tenants/t1/tools",
            json={
                "name": "math_sqrt",
                "handler_ref": "math:sqrt",
                "description": "Square root",
                "parameters_schema": {"type": "object"},
                "risk_tier": "low",
                "is_state_changing": False,
                "timeout_ms": 5000,
            },
            headers=_headers("t1"),
        )
        assert resp.status_code == 201, resp.text

    # -- Second app instance pointing to the same db (simulates restart)
    # TestClient context manager triggers startup lifespan → hydrate_tenant_registries
    with TestClient(_build_sqlite_app(db_path), raise_server_exceptions=True) as client2:
        resp2 = client2.get("/tenants/t1/tools", headers=_headers("t1"))
        assert resp2.status_code == 200, resp2.text
        names = [t["name"] for t in resp2.json()["tools"]]
        assert "math_sqrt" in names


def test_multiple_tools_survive_restart(tmp_path: Path) -> None:
    """Register multiple tools for the same tenant; all are hydrated after restart."""
    db_path = tmp_path / "exo.db"

    with TestClient(_build_sqlite_app(db_path), raise_server_exceptions=True) as client1:
        for tool_name in ("tool_a", "tool_b", "tool_c"):
            resp = client1.post(
                "/tenants/t1/tools",
                json={
                    "name": tool_name,
                    "handler_ref": "math:sqrt",
                    "description": f"Tool {tool_name}",
                    "parameters_schema": {},
                    "risk_tier": "low",
                    "is_state_changing": False,
                    "timeout_ms": 5000,
                },
                headers=_headers("t1"),
            )
            assert resp.status_code == 201

    with TestClient(_build_sqlite_app(db_path)) as client2:
        resp2 = client2.get("/tenants/t1/tools", headers=_headers("t1"))
        assert resp2.status_code == 200
        names = sorted(t["name"] for t in resp2.json()["tools"])
        assert names == ["tool_a", "tool_b", "tool_c"]


def test_tool_delete_is_persisted(tmp_path: Path) -> None:
    """Deleted tool is not hydrated on restart."""
    db_path = tmp_path / "exo.db"

    with TestClient(_build_sqlite_app(db_path), raise_server_exceptions=True) as client1:
        client1.post(
            "/tenants/t1/tools",
            json={
                "name": "transient_tool",
                "handler_ref": "math:sqrt",
                "description": "Will be deleted",
                "parameters_schema": {},
                "risk_tier": "low",
                "is_state_changing": False,
                "timeout_ms": 5000,
            },
            headers=_headers("t1"),
        )
        del_resp = client1.delete("/tenants/t1/tools/transient_tool", headers=_headers("t1"))
        assert del_resp.status_code == 204

    with TestClient(_build_sqlite_app(db_path)) as client2:
        resp2 = client2.get("/tenants/t1/tools", headers=_headers("t1"))
        assert resp2.status_code == 200
        names = [t["name"] for t in resp2.json()["tools"]]
        assert "transient_tool" not in names


# ---------------------------------------------------------------------------
# Tests — agent persistence roundtrip
# ---------------------------------------------------------------------------


def test_agent_survives_restart(tmp_path: Path) -> None:
    """Register an agent, simulate restart, verify it is hydrated into the new app."""
    db_path = tmp_path / "exo.db"

    with TestClient(_build_sqlite_app(db_path), raise_server_exceptions=True) as client1:
        resp = client1.post(
            "/tenants/t1/agents",
            json={
                "agent_id": "agent-alpha",
                "role": "assistant",
                "capability_tags": ["tool_use"],
                "instructions": "Be helpful",
                "metadata": {"model": "gpt-4o-mini"},
            },
            headers=_headers("t1"),
        )
        assert resp.status_code == 201, resp.text

    with TestClient(_build_sqlite_app(db_path), raise_server_exceptions=True) as client2:
        resp2 = client2.get("/tenants/t1/agents", headers=_headers("t1"))
        assert resp2.status_code == 200, resp2.text
        ids = [a["agent_id"] for a in resp2.json()["agents"]]
        assert "agent-alpha" in ids


def test_agent_delete_is_persisted(tmp_path: Path) -> None:
    """Deleted agent is not hydrated on restart."""
    db_path = tmp_path / "exo.db"

    with TestClient(_build_sqlite_app(db_path), raise_server_exceptions=True) as client1:
        client1.post(
            "/tenants/t1/agents",
            json={
                "agent_id": "transient-agent",
                "role": "assistant",
                "capability_tags": [],
                "instructions": "Temp",
                "metadata": {},
            },
            headers=_headers("t1"),
        )
        del_resp = client1.delete("/tenants/t1/agents/transient-agent", headers=_headers("t1"))
        assert del_resp.status_code == 204

    with TestClient(_build_sqlite_app(db_path)) as client2:
        resp2 = client2.get("/tenants/t1/agents", headers=_headers("t1"))
        assert resp2.status_code == 200
        ids = [a["agent_id"] for a in resp2.json()["agents"]]
        assert "transient-agent" not in ids


# ---------------------------------------------------------------------------
# Tests — tenant isolation
# ---------------------------------------------------------------------------


def test_tool_tenant_isolation_after_restart(tmp_path: Path) -> None:
    """Tools registered for t1 are not visible under t2 after hydration."""
    db_path = tmp_path / "exo.db"

    with TestClient(_build_sqlite_app(db_path), raise_server_exceptions=True) as client1:
        client1.post(
            "/tenants/t1/tools",
            json={
                "name": "t1_only",
                "handler_ref": "math:sqrt",
                "description": "Tenant 1 only",
                "parameters_schema": {},
                "risk_tier": "low",
                "is_state_changing": False,
                "timeout_ms": 5000,
            },
            headers=_headers("t1"),
        )

    with TestClient(_build_sqlite_app(db_path)) as client2:
        resp_t2 = client2.get("/tenants/t2/tools", headers=_headers("t2"))
        assert resp_t2.status_code == 200
        names = [t["name"] for t in resp_t2.json()["tools"]]
        assert "t1_only" not in names

        resp_t1 = client2.get("/tenants/t1/tools", headers=_headers("t1"))
        assert resp_t1.status_code == 200
        names_t1 = [t["name"] for t in resp_t1.json()["tools"]]
        assert "t1_only" in names_t1


# ---------------------------------------------------------------------------
# Tests — existing tests unaffected (memory backend)
# ---------------------------------------------------------------------------


def test_build_test_app_still_works_in_memory() -> None:
    """build_test_app() uses memory backend — no SQLite, stores are None."""
    app = build_test_app()
    assert getattr(app.state, "tool_store", None) is None
    assert getattr(app.state, "agent_store", None) is None

    client = TestClient(app)
    resp = client.post(
        "/tenants/t1/tools",
        json={
            "name": "in_memory_tool",
            "handler_ref": "math:sqrt",
            "description": "In memory",
            "parameters_schema": {},
            "risk_tier": "low",
            "is_state_changing": False,
            "timeout_ms": 5000,
        },
        headers=_headers("t1"),
    )
    assert resp.status_code == 201

    resp2 = client.get("/tenants/t1/tools", headers=_headers("t1"))
    assert resp2.status_code == 200
    names = [t["name"] for t in resp2.json()["tools"]]
    assert "in_memory_tool" in names
