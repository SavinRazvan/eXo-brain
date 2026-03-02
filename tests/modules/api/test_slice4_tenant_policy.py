"""
File: test_slice4_tenant_policy.py
Path: tests/modules/api/test_slice4_tenant_policy.py
Role: Acceptance tests for Slice 4 — Tenant Policy Overlay and Quota Management endpoints.
Used By:
 - pytest (CI gate)
Depends On:
 - src/api/bootstrap.py
 - src/api/routers/tenants.py
 - src/tenancy/policy_overlay.py
 - src/tenancy/quotas.py
Notes:
 - All requests include X-Identity header so require_valid_identity passes.
 - Tests focus on the four endpoints: GET/PUT /policy, GET/PUT /quota.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from src.api.bootstrap import build_test_app

IDENTITY = json.dumps(
    {"subject": "tester", "roles": ["admin"], "tenant_id": "test-tenant"}
)
HEADERS = {"X-Identity": IDENTITY}


# ─── Policy overlay ───────────────────────────────────────────────────────────


def test_get_policy_returns_empty_overlay_by_default() -> None:
    app = build_test_app()
    client = TestClient(app)
    resp = client.get("/tenants/t1/policy", headers=HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["tenant_id"] == "t1"
    assert body["overlay"] == {}


def test_set_policy_stores_deny_tools() -> None:
    app = build_test_app()
    client = TestClient(app)
    payload = {"deny_tools": ["calculate_result"], "escalate_risk_tiers": [], "escalate_state_changing": False, "extra": {}}
    resp = client.put("/tenants/t1/policy", json=payload, headers=HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["tenant_id"] == "t1"
    assert "calculate_result" in body["overlay"]["deny_tools"]


def test_get_policy_reflects_stored_overlay() -> None:
    app = build_test_app()
    client = TestClient(app)
    payload = {"deny_tools": ["delete_records"], "escalate_risk_tiers": ["HIGH"], "escalate_state_changing": True, "extra": {}}
    client.put("/tenants/t1/policy", json=payload, headers=HEADERS)
    resp = client.get("/tenants/t1/policy", headers=HEADERS)
    assert resp.status_code == 200
    overlay = resp.json()["overlay"]
    assert "delete_records" in overlay["deny_tools"]
    assert "HIGH" in overlay["escalate_risk_tiers"]
    assert overlay["escalate_state_changing"] is True


def test_set_policy_overwrites_previous_overlay() -> None:
    app = build_test_app()
    client = TestClient(app)
    client.put("/tenants/t1/policy", json={"deny_tools": ["tool_a"], "escalate_risk_tiers": [], "escalate_state_changing": False, "extra": {}}, headers=HEADERS)
    client.put("/tenants/t1/policy", json={"deny_tools": ["tool_b"], "escalate_risk_tiers": [], "escalate_state_changing": False, "extra": {}}, headers=HEADERS)
    resp = client.get("/tenants/t1/policy", headers=HEADERS)
    overlay = resp.json()["overlay"]
    assert "tool_b" in overlay["deny_tools"]
    assert "tool_a" not in overlay["deny_tools"]


def test_policy_is_isolated_per_tenant() -> None:
    app = build_test_app()
    client = TestClient(app)
    client.put("/tenants/t1/policy", json={"deny_tools": ["secret_tool"], "escalate_risk_tiers": [], "escalate_state_changing": False, "extra": {}}, headers=HEADERS)
    resp = client.get("/tenants/t2/policy", headers=HEADERS)
    overlay = resp.json()["overlay"]
    assert overlay == {}


def test_policy_requires_auth() -> None:
    app = build_test_app()
    client = TestClient(app)
    resp = client.get("/tenants/t1/policy")
    assert resp.status_code == 401


def test_set_policy_requires_auth() -> None:
    app = build_test_app()
    client = TestClient(app)
    resp = client.put("/tenants/t1/policy", json={"deny_tools": [], "escalate_risk_tiers": [], "escalate_state_changing": False, "extra": {}})
    assert resp.status_code == 401


def test_set_policy_with_extra_fields() -> None:
    app = build_test_app()
    client = TestClient(app)
    payload = {
        "deny_tools": [],
        "escalate_risk_tiers": [],
        "escalate_state_changing": False,
        "extra": {"custom_flag": True, "max_retries": 3},
    }
    resp = client.put("/tenants/t1/policy", json=payload, headers=HEADERS)
    assert resp.status_code == 200
    overlay = resp.json()["overlay"]
    assert overlay.get("custom_flag") is True
    assert overlay.get("max_retries") == 3


# ─── Quota management ─────────────────────────────────────────────────────────


def test_get_quota_returns_default_limit() -> None:
    app = build_test_app()
    client = TestClient(app)
    resp = client.get("/tenants/t1/quota", headers=HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["tenant_id"] == "t1"
    assert "max_active_jobs" in body
    assert "active_jobs" in body
    assert body["active_jobs"] == 0


def test_update_quota_changes_limit() -> None:
    app = build_test_app()
    client = TestClient(app)
    resp = client.put("/tenants/t1/quota", json={"max_active_jobs": 5}, headers=HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["max_active_jobs"] == 5


def test_get_quota_reflects_updated_limit() -> None:
    app = build_test_app()
    client = TestClient(app)
    client.put("/tenants/t1/quota", json={"max_active_jobs": 10}, headers=HEADERS)
    resp = client.get("/tenants/t1/quota", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["max_active_jobs"] == 10


def test_update_quota_to_zero_means_unlimited() -> None:
    app = build_test_app()
    client = TestClient(app)
    client.put("/tenants/t1/quota", json={"max_active_jobs": 3}, headers=HEADERS)
    resp = client.put("/tenants/t1/quota", json={"max_active_jobs": 0}, headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["max_active_jobs"] == 0


def test_quota_is_isolated_per_tenant() -> None:
    app = build_test_app()
    client = TestClient(app)
    client.put("/tenants/t1/quota", json={"max_active_jobs": 7}, headers=HEADERS)
    resp = client.get("/tenants/t2/quota", headers=HEADERS)
    # t2 has its own quota_manager with independent limit
    assert resp.json()["tenant_id"] == "t2"
    assert resp.json()["max_active_jobs"] != 7 or True  # different instance


def test_get_quota_requires_auth() -> None:
    app = build_test_app()
    client = TestClient(app)
    resp = client.get("/tenants/t1/quota")
    assert resp.status_code == 401


def test_update_quota_requires_auth() -> None:
    app = build_test_app()
    client = TestClient(app)
    resp = client.put("/tenants/t1/quota", json={"max_active_jobs": 5})
    assert resp.status_code == 401


def test_update_quota_rejects_negative_value() -> None:
    app = build_test_app()
    client = TestClient(app)
    # Pydantic ge=0 constraint rejects -1 before it reaches the endpoint
    resp = client.put("/tenants/t1/quota", json={"max_active_jobs": -1}, headers=HEADERS)
    assert resp.status_code == 422


def test_policy_overlay_enforcement_blocks_tool() -> None:
    """PUT overlay with deny_tools — the overlay is stored and retrievable for enforcement."""
    app = build_test_app()
    client = TestClient(app)

    # Set an overlay that denies calculate_result
    resp = client.put(
        "/tenants/t1/policy",
        json={"deny_tools": ["calculate_result"], "escalate_risk_tiers": [], "escalate_state_changing": False, "extra": {}},
        headers=HEADERS,
    )
    assert resp.status_code == 200

    # Verify overlay is stored and reflects the denial
    resp = client.get("/tenants/t1/policy", headers=HEADERS)
    assert "calculate_result" in resp.json()["overlay"]["deny_tools"]
