"""
File: test_slice2_tools_agents.py
Path: tests/modules/api/test_slice2_tools_agents.py
Role: Acceptance tests for Slice 2 — Tool & Agent Management API endpoints.
Used By:
 - pytest
Depends On:
 - src/api/routers/tools.py
 - src/api/routers/agents.py
 - src/api/bootstrap.py
Notes:
 - handler_ref tests use 'math:sqrt' as a known resolvable stdlib function.
 - All tests create fresh isolated app instances to prevent cross-test pollution.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from src.api.bootstrap import build_test_app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _headers(tenant_id: str = "t1", roles: list[str] | None = None) -> dict:
    payload = {"subject": "user@test.com", "roles": roles or ["user"], "tenant_id": tenant_id,
               "token_validation_state": "valid"}
    return {"X-Identity": json.dumps(payload)}


def _client(tenant_id: str = "t1") -> tuple[TestClient, str]:
    """Return (client, tenant_id) with a fresh isolated app."""
    app = build_test_app()
    return TestClient(app), tenant_id


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


def test_register_tool_success() -> None:
    client, tid = _client()
    resp = client.post(
        f"/tenants/{tid}/tools",
        json={
            "name": "add_numbers",
            "handler_ref": "math:sqrt",
            "description": "Computes sqrt",
            "parameters_schema": {"type": "object", "properties": {}},
            "risk_tier": "low",
            "is_state_changing": False,
            "timeout_ms": 5000,
        },
        headers=_headers(tid),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "add_numbers"
    assert body["description"] == "Computes sqrt"
    assert body["risk_tier"] == "low"
    assert body["is_state_changing"] is False


def test_register_tool_returns_422_for_unresolvable_handler_ref() -> None:
    client, tid = _client()
    resp = client.post(
        f"/tenants/{tid}/tools",
        json={"name": "broken", "handler_ref": "nonexistent.module:fn"},
        headers=_headers(tid),
    )
    assert resp.status_code == 422


def test_register_tool_returns_422_for_malformed_handler_ref() -> None:
    client, tid = _client()
    resp = client.post(
        f"/tenants/{tid}/tools",
        json={"name": "broken", "handler_ref": "no_colon_here"},
        headers=_headers(tid),
    )
    assert resp.status_code == 422


def test_register_tool_returns_422_for_missing_function_in_module() -> None:
    client, tid = _client()
    resp = client.post(
        f"/tenants/{tid}/tools",
        json={"name": "broken", "handler_ref": "math:nonexistent_function"},
        headers=_headers(tid),
    )
    assert resp.status_code == 422


def test_register_tool_returns_409_for_duplicate_name() -> None:
    client, tid = _client()
    payload = {"name": "dup_tool", "handler_ref": "math:sqrt"}
    client.post(f"/tenants/{tid}/tools", json=payload, headers=_headers(tid))
    resp = client.post(f"/tenants/{tid}/tools", json=payload, headers=_headers(tid))
    assert resp.status_code == 409


def test_register_tool_returns_401_without_identity() -> None:
    client, tid = _client()
    resp = client.post(
        f"/tenants/{tid}/tools",
        json={"name": "t", "handler_ref": "math:sqrt"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Tool list
# ---------------------------------------------------------------------------


def test_list_tools_returns_empty_for_new_tenant() -> None:
    client, tid = _client("empty-tenant")
    resp = client.get(f"/tenants/{tid}/tools", headers=_headers(tid))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["tools"] == []


def test_list_tools_includes_registered_tool() -> None:
    client, tid = _client()
    client.post(
        f"/tenants/{tid}/tools",
        json={"name": "listed_tool", "handler_ref": "math:sqrt"},
        headers=_headers(tid),
    )
    resp = client.get(f"/tenants/{tid}/tools", headers=_headers(tid))
    assert resp.status_code == 200
    names = [t["name"] for t in resp.json()["tools"]]
    assert "listed_tool" in names
    assert resp.json()["total"] == 1


# ---------------------------------------------------------------------------
# Tool get
# ---------------------------------------------------------------------------


def test_get_tool_returns_full_descriptor() -> None:
    client, tid = _client()
    client.post(
        f"/tenants/{tid}/tools",
        json={"name": "my_tool", "handler_ref": "math:sqrt", "description": "sqrt fn"},
        headers=_headers(tid),
    )
    resp = client.get(f"/tenants/{tid}/tools/my_tool", headers=_headers(tid))
    assert resp.status_code == 200
    assert resp.json()["name"] == "my_tool"
    assert resp.json()["description"] == "sqrt fn"


def test_get_tool_returns_404_for_unknown_name() -> None:
    client, tid = _client()
    resp = client.get(f"/tenants/{tid}/tools/ghost_tool", headers=_headers(tid))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tool delete
# ---------------------------------------------------------------------------


def test_delete_tool_removes_it_from_list() -> None:
    client, tid = _client()
    client.post(
        f"/tenants/{tid}/tools",
        json={"name": "to_delete", "handler_ref": "math:sqrt"},
        headers=_headers(tid),
    )
    del_resp = client.delete(f"/tenants/{tid}/tools/to_delete", headers=_headers(tid))
    assert del_resp.status_code == 204

    list_resp = client.get(f"/tenants/{tid}/tools", headers=_headers(tid))
    assert list_resp.json()["total"] == 0


def test_delete_tool_returns_404_for_unknown_name() -> None:
    client, tid = _client()
    resp = client.delete(f"/tenants/{tid}/tools/ghost", headers=_headers(tid))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tool tenant isolation
# ---------------------------------------------------------------------------


def test_tools_isolated_across_tenants() -> None:
    app = build_test_app()
    client = TestClient(app)

    client.post(
        "/tenants/ta/tools",
        json={"name": "ta_tool", "handler_ref": "math:sqrt"},
        headers=_headers("ta"),
    )

    resp_ta = client.get("/tenants/ta/tools", headers=_headers("ta"))
    resp_tb = client.get("/tenants/tb/tools", headers=_headers("tb"))

    assert resp_ta.json()["total"] == 1
    assert resp_tb.json()["total"] == 0


# ---------------------------------------------------------------------------
# Agent registration
# ---------------------------------------------------------------------------


def test_register_agent_success() -> None:
    client, tid = _client()
    resp = client.post(
        f"/tenants/{tid}/agents",
        json={
            "agent_id": "math-agent",
            "role": "math_assistant",
            "capability_tags": ["tool_use"],
            "instructions": "You are a math agent.",
            "metadata": {"model": "gpt-4o-mini"},
        },
        headers=_headers(tid),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["agent_id"] == "math-agent"
    assert body["role"] == "math_assistant"
    assert body["instructions"] == "You are a math agent."
    assert "tool_use" in body["capability_tags"]
    assert body["metadata"]["model"] == "gpt-4o-mini"


def test_register_agent_returns_409_for_duplicate_id() -> None:
    client, tid = _client()
    payload = {"agent_id": "dup-agent", "role": "dup_role"}
    client.post(f"/tenants/{tid}/agents", json=payload, headers=_headers(tid))
    resp = client.post(f"/tenants/{tid}/agents", json=payload, headers=_headers(tid))
    assert resp.status_code == 409


def test_register_agent_returns_401_without_identity() -> None:
    client, tid = _client()
    resp = client.post(f"/tenants/{tid}/agents", json={"agent_id": "a", "role": "r"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Agent list / get / delete
# ---------------------------------------------------------------------------


def test_list_agents_returns_empty_for_new_tenant() -> None:
    client, tid = _client("empty-agents-tenant")
    resp = client.get(f"/tenants/{tid}/agents", headers=_headers(tid))
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


def test_list_agents_includes_registered_agent() -> None:
    client, tid = _client()
    client.post(
        f"/tenants/{tid}/agents",
        json={"agent_id": "list-a", "role": "list_role"},
        headers=_headers(tid),
    )
    resp = client.get(f"/tenants/{tid}/agents", headers=_headers(tid))
    ids = [a["agent_id"] for a in resp.json()["agents"]]
    assert "list-a" in ids


def test_get_agent_returns_full_spec() -> None:
    client, tid = _client()
    client.post(
        f"/tenants/{tid}/agents",
        json={"agent_id": "get-a", "role": "get_role", "instructions": "hello"},
        headers=_headers(tid),
    )
    resp = client.get(f"/tenants/{tid}/agents/get-a", headers=_headers(tid))
    assert resp.status_code == 200
    assert resp.json()["instructions"] == "hello"


def test_get_agent_returns_404_for_unknown_id() -> None:
    client, tid = _client()
    resp = client.get(f"/tenants/{tid}/agents/ghost-agent", headers=_headers(tid))
    assert resp.status_code == 404


def test_delete_agent_removes_from_list() -> None:
    client, tid = _client()
    client.post(
        f"/tenants/{tid}/agents",
        json={"agent_id": "del-a", "role": "del_role"},
        headers=_headers(tid),
    )
    del_resp = client.delete(f"/tenants/{tid}/agents/del-a", headers=_headers(tid))
    assert del_resp.status_code == 204

    list_resp = client.get(f"/tenants/{tid}/agents", headers=_headers(tid))
    assert list_resp.json()["total"] == 0


def test_delete_agent_returns_404_for_unknown() -> None:
    client, tid = _client()
    resp = client.delete(f"/tenants/{tid}/agents/ghost", headers=_headers(tid))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Handoff routes
# ---------------------------------------------------------------------------


def _register_two_agents(client: TestClient, tid: str) -> None:
    client.post(
        f"/tenants/{tid}/agents",
        json={"agent_id": "src-agent", "role": "source_role", "capability_tags": ["tool_use"]},
        headers=_headers(tid),
    )
    client.post(
        f"/tenants/{tid}/agents",
        json={"agent_id": "tgt-agent", "role": "target_role", "capability_tags": ["tool_use"]},
        headers=_headers(tid),
    )


def test_add_handoff_route_success() -> None:
    client, tid = _client()
    _register_two_agents(client, tid)
    resp = client.post(
        f"/tenants/{tid}/agents/routes",
        json={
            "source_role": "source_role",
            "target_role": "target_role",
            "reason": "escalate",
            "required_target_capabilities": ["tool_use"],
        },
        headers=_headers(tid, roles=["entitlement_pro"]),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["source_role"] == "source_role"
    assert body["target_role"] == "target_role"


def test_add_handoff_route_returns_422_for_unknown_source_role() -> None:
    client, tid = _client()
    resp = client.post(
        f"/tenants/{tid}/agents/routes",
        json={"source_role": "ghost_role", "target_role": "also_ghost"},
        headers=_headers(tid, roles=["entitlement_pro"]),
    )
    assert resp.status_code == 422


def test_handoff_route_requires_pro_entitlement_and_emits_audit() -> None:
    app = build_test_app()
    client = TestClient(app)
    tid = "t1"
    _register_two_agents(client, tid)
    resp = client.post(
        f"/tenants/{tid}/agents/routes",
        json={"source_role": "source_role", "target_role": "target_role"},
        headers=_headers(tid, roles=["user"]),
    )
    assert resp.status_code == 403
    assert "ENTITLEMENT_TIER_REQUIRED" in resp.text

    records = asyncio.run(app.state.audit_store.list_audit_events(tenant_id=tid, limit=20))
    entitlement = [record for record in records if record.event_type == "entitlement_decision"]
    assert entitlement
    latest = entitlement[-1]
    assert latest.payload.get("surface") == "agent_routing_controls"
    assert latest.payload.get("feature") == "governance.agent_routing.advanced"
    assert latest.payload.get("decision") == "deny"
    assert latest.payload.get("required_tier") == "pro"


def test_list_handoff_routes_returns_registered_route() -> None:
    client, tid = _client()
    _register_two_agents(client, tid)
    client.post(
        f"/tenants/{tid}/agents/routes",
        json={"source_role": "source_role", "target_role": "target_role", "reason": "reason1"},
        headers=_headers(tid, roles=["entitlement_pro"]),
    )
    resp = client.get(f"/tenants/{tid}/agents/routes", headers=_headers(tid, roles=["entitlement_pro"]))
    assert resp.status_code == 200
    routes = resp.json()
    assert any(r["source_role"] == "source_role" and r["target_role"] == "target_role" for r in routes)


def test_list_handoff_routes_returns_empty_for_no_routes() -> None:
    client, tid = _client("no-routes-tenant")
    resp = client.get(f"/tenants/{tid}/agents/routes", headers=_headers(tid, roles=["entitlement_pro"]))
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# Handoff fallback policies
# ---------------------------------------------------------------------------


def test_set_fallback_policy_success() -> None:
    client, tid = _client()
    # Register three agents: src, primary target, fallback target
    for aid, role in [("fa", "fallback_src"), ("fb", "fallback_tgt"), ("fc", "fallback_alt")]:
        client.post(
            f"/tenants/{tid}/agents",
            json={"agent_id": aid, "role": role},
            headers=_headers(tid),
        )
    resp = client.post(
        f"/tenants/{tid}/agents/fallback",
        json={
            "source_role": "fallback_src",
            "target_role": "fallback_tgt",
            "fallback_target_roles": ["fallback_alt"],
            "target_role_priorities": {},
        },
        headers=_headers(tid, roles=["entitlement_pro"]),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["source_role"] == "fallback_src"
    assert "fallback_alt" in body["fallback_target_roles"]


def test_list_fallback_policies_returns_registered_policy() -> None:
    client, tid = _client()
    for aid, role in [("p1", "p_src"), ("p2", "p_tgt")]:
        client.post(
            f"/tenants/{tid}/agents",
            json={"agent_id": aid, "role": role},
            headers=_headers(tid),
        )
    client.post(
        f"/tenants/{tid}/agents/fallback",
        json={"source_role": "p_src", "target_role": "p_tgt", "fallback_target_roles": []},
        headers=_headers(tid, roles=["entitlement_pro"]),
    )
    resp = client.get(f"/tenants/{tid}/agents/fallback", headers=_headers(tid, roles=["entitlement_pro"]))
    assert resp.status_code == 200
    policies = resp.json()
    assert any(p["source_role"] == "p_src" for p in policies)
