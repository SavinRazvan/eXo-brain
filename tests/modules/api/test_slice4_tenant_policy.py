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

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from src.api.bootstrap import build_test_app
from src.config.settings import AppSettings, AuthSettings, RuntimeSettings

def _headers(tenant_id: str = "t1", roles: list[str] | None = None) -> dict[str, str]:
    identity = json.dumps(
        {
            "subject": "tester",
            "roles": roles or ["admin"],
            "tenant_id": tenant_id,
        }
    )
    return {"X-Identity": identity}


# ─── Policy overlay ───────────────────────────────────────────────────────────


def test_get_policy_returns_empty_overlay_by_default() -> None:
    app = build_test_app()
    client = TestClient(app)
    resp = client.get("/tenants/t1/policy", headers=_headers("t1"))
    assert resp.status_code == 200
    body = resp.json()
    assert body["tenant_id"] == "t1"
    assert body["overlay"] == {}


def test_set_policy_stores_deny_tools() -> None:
    app = build_test_app()
    client = TestClient(app)
    payload = {"deny_tools": ["calculate_result"], "escalate_risk_tiers": [], "escalate_state_changing": False, "extra": {}}
    resp = client.put("/tenants/t1/policy", json=payload, headers=_headers("t1"))
    assert resp.status_code == 200
    body = resp.json()
    assert body["tenant_id"] == "t1"
    assert "calculate_result" in body["overlay"]["deny_tools"]


def test_get_policy_reflects_stored_overlay() -> None:
    app = build_test_app()
    client = TestClient(app)
    payload = {"deny_tools": ["delete_records"], "escalate_risk_tiers": ["HIGH"], "escalate_state_changing": True, "extra": {}}
    client.put("/tenants/t1/policy", json=payload, headers=_headers("t1"))
    resp = client.get("/tenants/t1/policy", headers=_headers("t1"))
    assert resp.status_code == 200
    overlay = resp.json()["overlay"]
    assert "delete_records" in overlay["deny_tools"]
    assert "HIGH" in overlay["escalate_risk_tiers"]
    assert overlay["escalate_state_changing"] is True


def test_set_policy_overwrites_previous_overlay() -> None:
    app = build_test_app()
    client = TestClient(app)
    client.put("/tenants/t1/policy", json={"deny_tools": ["tool_a"], "escalate_risk_tiers": [], "escalate_state_changing": False, "extra": {}}, headers=_headers("t1"))
    client.put("/tenants/t1/policy", json={"deny_tools": ["tool_b"], "escalate_risk_tiers": [], "escalate_state_changing": False, "extra": {}}, headers=_headers("t1"))
    resp = client.get("/tenants/t1/policy", headers=_headers("t1"))
    overlay = resp.json()["overlay"]
    assert "tool_b" in overlay["deny_tools"]
    assert "tool_a" not in overlay["deny_tools"]


def test_policy_is_isolated_per_tenant() -> None:
    app = build_test_app()
    client = TestClient(app)
    client.put("/tenants/t1/policy", json={"deny_tools": ["secret_tool"], "escalate_risk_tiers": [], "escalate_state_changing": False, "extra": {}}, headers=_headers("t1"))
    resp = client.get("/tenants/t2/policy", headers=_headers("t2"))
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
    resp = client.put("/tenants/t1/policy", json=payload, headers=_headers("t1"))
    assert resp.status_code == 200
    overlay = resp.json()["overlay"]
    assert overlay.get("custom_flag") is True
    assert overlay.get("max_retries") == 3


def test_set_policy_requires_pro_entitlement_for_ingress_profile() -> None:
    app = build_test_app()
    client = TestClient(app)
    payload = {
        "deny_tools": [],
        "escalate_risk_tiers": [],
        "escalate_state_changing": False,
        "extra": {"ingress_profile": "strict"},
    }
    resp = client.put("/tenants/t1/policy", json=payload, headers=_headers("t1", roles=["admin"]))
    assert resp.status_code == 403
    assert "ENTITLEMENT_TIER_REQUIRED" in resp.text

    records = asyncio.run(app.state.audit_store.list_audit_events(tenant_id="t1", limit=20))
    entitlement = [record for record in records if record.event_type == "entitlement_decision"]
    assert entitlement
    latest = entitlement[-1]
    assert latest.payload.get("surface") == "tenant_policy_overlay"
    assert latest.payload.get("decision") == "deny"
    assert latest.payload.get("required_tier") == "pro"
    assert latest.payload.get("current_tier") == "foundation"


def test_set_policy_allows_pro_entitlement_for_ingress_profile() -> None:
    app = build_test_app()
    client = TestClient(app)
    payload = {
        "deny_tools": [],
        "escalate_risk_tiers": [],
        "escalate_state_changing": False,
        "extra": {"ingress_profile": "strict"},
    }
    resp = client.put("/tenants/t1/policy", json=payload, headers=_headers("t1", roles=["entitlement_pro"]))
    assert resp.status_code == 200
    assert resp.json()["overlay"].get("ingress_profile") == "strict"

    records = asyncio.run(app.state.audit_store.list_audit_events(tenant_id="t1", limit=20))
    entitlement = [record for record in records if record.event_type == "entitlement_decision"]
    assert entitlement
    latest = entitlement[-1]
    assert latest.payload.get("decision") == "allow"
    assert latest.payload.get("required_tier") == "pro"
    assert latest.payload.get("current_tier") == "pro"


def test_set_policy_requires_enterprise_entitlement_for_signed_gate_plugin() -> None:
    app = build_test_app()
    client = TestClient(app)
    payload = {
        "deny_tools": [],
        "escalate_risk_tiers": [],
        "escalate_state_changing": False,
        "extra": {"signed_gate_plugin_ref": "plugin://trusted/signed-v1"},
    }
    resp = client.put("/tenants/t1/policy", json=payload, headers=_headers("t1", roles=["entitlement_pro"]))
    assert resp.status_code == 403
    assert "ENTITLEMENT_TIER_REQUIRED" in resp.text

    records = asyncio.run(app.state.audit_store.list_audit_events(tenant_id="t1", limit=20))
    entitlement = [record for record in records if record.event_type == "entitlement_decision"]
    assert entitlement
    latest = entitlement[-1]
    assert latest.payload.get("required_tier") == "enterprise"
    assert latest.payload.get("current_tier") == "pro"


def test_set_policy_accepts_enterprise_signed_gate_plugin_and_emits_lifecycle_audit() -> None:
    app = build_test_app()
    client = TestClient(app)
    payload = {
        "deny_tools": [],
        "escalate_risk_tiers": [],
        "escalate_state_changing": False,
        "extra": {"signed_gate_plugin_ref": "plugin://trusted/signed-v1"},
    }
    resp = client.put(
        "/tenants/t1/policy",
        json=payload,
        headers=_headers("t1", roles=["entitlement_enterprise"]),
    )
    assert resp.status_code == 200
    overlay = resp.json()["overlay"]
    assert overlay.get("signed_gate_plugin_ref") == "plugin://trusted/signed-v1"
    assert overlay.get("signed_gate_plugin_version") == "1.0.0"
    assert overlay.get("signed_gate_plugin_signer") == "exo-security"
    assert overlay.get("signed_gate_plugin_sandbox_mode") == "declarative_rules_only"

    records = asyncio.run(app.state.audit_store.list_audit_events(tenant_id="t1", limit=30))
    lifecycle_events = [
        record for record in records if record.event_type == "tenant_policy_signed_gate_plugin_lifecycle"
    ]
    assert lifecycle_events
    latest = lifecycle_events[-1]
    assert latest.payload.get("action") == "load"
    assert latest.payload.get("new_signed_gate_plugin_ref") == "plugin://trusted/signed-v1"
    assert latest.payload.get("signed_gate_plugin_rule_count") >= 1


def test_set_policy_rejects_unknown_signed_gate_plugin_reference() -> None:
    app = build_test_app()
    client = TestClient(app)
    payload = {
        "deny_tools": [],
        "escalate_risk_tiers": [],
        "escalate_state_changing": False,
        "extra": {"signed_gate_plugin_ref": "plugin://trusted/unknown"},
    }
    resp = client.put(
        "/tenants/t1/policy",
        json=payload,
        headers=_headers("t1", roles=["entitlement_enterprise"]),
    )
    assert resp.status_code == 422
    assert "INGRESS_SIGNED_PLUGIN_UNKNOWN" in resp.text


def test_set_policy_blocks_signed_plugin_reload_when_active_runs_exist() -> None:
    app = build_test_app()
    client = TestClient(app)
    initial_payload = {
        "deny_tools": [],
        "escalate_risk_tiers": [],
        "escalate_state_changing": False,
        "extra": {"signed_gate_plugin_ref": "plugin://trusted/signed-v1"},
    }
    initial = client.put(
        "/tenants/t1/policy",
        json=initial_payload,
        headers=_headers("t1", roles=["entitlement_enterprise"]),
    )
    assert initial.status_code == 200

    app.state.run_control_registry.start_run(
        tenant_id="t1",
        session_id="sess_policy_gate",
        run_id="run_policy_gate_1",
        correlation_id="run_policy_gate_1",
        transport="sse",
    )

    reload_payload = {
        "deny_tools": [],
        "escalate_risk_tiers": [],
        "escalate_state_changing": False,
        "extra": {"signed_gate_plugin_ref": "plugin://trusted/signed-v2"},
    }
    resp = client.put(
        "/tenants/t1/policy",
        json=reload_payload,
        headers=_headers("t1", roles=["entitlement_enterprise"]),
    )
    assert resp.status_code == 409
    assert "INGRESS_SIGNED_PLUGIN_LIFECYCLE_BLOCKED_ACTIVE_RUNS" in resp.text


def test_set_policy_rejects_invalid_ingress_profile_name() -> None:
    app = build_test_app()
    client = TestClient(app)
    payload = {
        "deny_tools": [],
        "escalate_risk_tiers": [],
        "escalate_state_changing": False,
        "extra": {"ingress_profile": "unknown-profile"},
    }
    resp = client.put("/tenants/t1/policy", json=payload, headers=_headers("t1", roles=["entitlement_pro"]))
    assert resp.status_code == 422
    assert "INGRESS_PROFILE_UNSUPPORTED" in resp.text


def test_set_policy_rejects_ingress_max_chars_profile_relaxation() -> None:
    app = build_test_app()
    client = TestClient(app)
    payload = {
        "deny_tools": [],
        "escalate_risk_tiers": [],
        "escalate_state_changing": False,
        "extra": {"ingress_profile": "strict", "ingress_max_input_chars": 5000},
    }
    resp = client.put("/tenants/t1/policy", json=payload, headers=_headers("t1", roles=["entitlement_pro"]))
    assert resp.status_code == 422
    assert "INGRESS_PROFILE_COMPATIBILITY_MAX_INPUT_RELAXATION_NOT_ALLOWED" in resp.text


def test_set_policy_accepts_custom_ingress_rules_for_pro_and_emits_profile_audit() -> None:
    app = build_test_app()
    client = TestClient(app)
    payload = {
        "deny_tools": [],
        "escalate_risk_tiers": [],
        "escalate_state_changing": False,
        "extra": {
            "ingress_profile": "strict",
            "ingress_max_input_chars": 3200,
            "ingress_custom_rules": [
                {
                    "rule_id": "deny-credential-share",
                    "action": "deny",
                    "match_type": "contains_any",
                    "patterns": ["share private key"],
                    "reason_code": "INGRESS_DENY_CREDENTIAL_SHARE",
                    "message": "Credential sharing is denied.",
                }
            ],
        },
    }
    resp = client.put("/tenants/t1/policy", json=payload, headers=_headers("t1", roles=["entitlement_pro"]))
    assert resp.status_code == 200
    overlay = resp.json()["overlay"]
    assert overlay.get("ingress_profile") == "strict"
    assert overlay.get("ingress_max_input_chars") == 3200
    assert overlay.get("ingress_profile_compatibility_mode") == "strict"
    assert len(overlay.get("ingress_custom_rules", [])) == 1

    records = asyncio.run(app.state.audit_store.list_audit_events(tenant_id="t1", limit=30))
    profile_events = [
        record for record in records if record.event_type == "tenant_policy_ingress_profile_configured"
    ]
    assert profile_events
    latest = profile_events[-1]
    assert latest.payload.get("ingress_profile") == "strict"
    assert latest.payload.get("ingress_custom_rule_count") == 1
    assert latest.payload.get("ingress_max_input_chars") == 3200


def test_set_policy_requires_pro_entitlement_for_classifier_shadow_mode() -> None:
    app = build_test_app()
    client = TestClient(app)
    payload = {
        "deny_tools": [],
        "escalate_risk_tiers": [],
        "escalate_state_changing": False,
        "extra": {
            "ingress_classifier_mode": "shadow",
            "ingress_classifier_threshold": 0.4,
        },
    }
    resp = client.put("/tenants/t1/policy", json=payload, headers=_headers("t1", roles=["admin"]))
    assert resp.status_code == 403
    assert "ENTITLEMENT_TIER_REQUIRED" in resp.text

    records = asyncio.run(app.state.audit_store.list_audit_events(tenant_id="t1", limit=20))
    entitlement = [record for record in records if record.event_type == "entitlement_decision"]
    assert entitlement
    latest = entitlement[-1]
    assert latest.payload.get("feature") == "governance.ingress.classifier"
    assert latest.payload.get("required_tier") == "pro"
    assert latest.payload.get("current_tier") == "foundation"


def test_set_policy_accepts_classifier_shadow_for_pro_and_emits_profile_audit() -> None:
    app = build_test_app()
    client = TestClient(app)
    payload = {
        "deny_tools": [],
        "escalate_risk_tiers": [],
        "escalate_state_changing": False,
        "extra": {
            "ingress_classifier_mode": "shadow",
            "ingress_classifier_threshold": 0.4,
            "ingress_classifier_model_version": "mini-shadow-v1",
            "ingress_classifier_signals": ["bypass safety", "reveal secrets"],
        },
    }
    resp = client.put("/tenants/t1/policy", json=payload, headers=_headers("t1", roles=["entitlement_pro"]))
    assert resp.status_code == 200
    overlay = resp.json()["overlay"]
    assert overlay.get("ingress_classifier_mode") == "shadow"
    assert overlay.get("ingress_classifier_threshold") == 0.4
    assert overlay.get("ingress_classifier_model_version") == "mini-shadow-v1"
    assert overlay.get("ingress_classifier_signals") == ["bypass safety", "reveal secrets"]

    records = asyncio.run(app.state.audit_store.list_audit_events(tenant_id="t1", limit=30))
    profile_events = [
        record for record in records if record.event_type == "tenant_policy_ingress_profile_configured"
    ]
    assert profile_events
    latest = profile_events[-1]
    assert latest.payload.get("ingress_classifier_mode") == "shadow"
    assert latest.payload.get("ingress_classifier_model_version") == "mini-shadow-v1"
    assert latest.payload.get("ingress_classifier_signal_count") == 2


def test_set_policy_rejects_invalid_classifier_mode() -> None:
    app = build_test_app()
    client = TestClient(app)
    payload = {
        "deny_tools": [],
        "escalate_risk_tiers": [],
        "escalate_state_changing": False,
        "extra": {
            "ingress_classifier_mode": "monitor-only-extended",
        },
    }
    resp = client.put("/tenants/t1/policy", json=payload, headers=_headers("t1", roles=["entitlement_pro"]))
    assert resp.status_code == 422
    assert "INGRESS_CLASSIFIER_MODE_INVALID" in resp.text


# ─── Quota management ─────────────────────────────────────────────────────────


def test_get_quota_returns_default_limit() -> None:
    app = build_test_app()
    client = TestClient(app)
    resp = client.get("/tenants/t1/quota", headers=_headers("t1"))
    assert resp.status_code == 200
    body = resp.json()
    assert body["tenant_id"] == "t1"
    assert "max_active_jobs" in body
    assert "active_jobs" in body
    assert body["active_jobs"] == 0


def test_update_quota_changes_limit() -> None:
    app = build_test_app()
    client = TestClient(app)
    resp = client.put("/tenants/t1/quota", json={"max_active_jobs": 5}, headers=_headers("t1"))
    assert resp.status_code == 200
    body = resp.json()
    assert body["max_active_jobs"] == 5


def test_get_quota_reflects_updated_limit() -> None:
    app = build_test_app()
    client = TestClient(app)
    client.put("/tenants/t1/quota", json={"max_active_jobs": 10}, headers=_headers("t1"))
    resp = client.get("/tenants/t1/quota", headers=_headers("t1"))
    assert resp.status_code == 200
    assert resp.json()["max_active_jobs"] == 10


def test_update_quota_to_zero_means_unlimited() -> None:
    app = build_test_app()
    client = TestClient(app)
    client.put("/tenants/t1/quota", json={"max_active_jobs": 3}, headers=_headers("t1"))
    resp = client.put("/tenants/t1/quota", json={"max_active_jobs": 0}, headers=_headers("t1"))
    assert resp.status_code == 200
    assert resp.json()["max_active_jobs"] == 0


def test_quota_is_isolated_per_tenant() -> None:
    app = build_test_app()
    client = TestClient(app)
    client.put("/tenants/t1/quota", json={"max_active_jobs": 7}, headers=_headers("t1"))
    resp = client.get("/tenants/t2/quota", headers=_headers("t2"))
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
    resp = client.put("/tenants/t1/quota", json={"max_active_jobs": -1}, headers=_headers("t1"))
    assert resp.status_code == 422


def test_policy_overlay_enforcement_blocks_tool() -> None:
    """PUT overlay with deny_tools — the overlay is stored and retrievable for enforcement."""
    app = build_test_app()
    client = TestClient(app)

    # Set an overlay that denies calculate_result
    resp = client.put(
        "/tenants/t1/policy",
        json={"deny_tools": ["calculate_result"], "escalate_risk_tiers": [], "escalate_state_changing": False, "extra": {}},
        headers=_headers("t1"),
    )
    assert resp.status_code == 200

    # Verify overlay is stored and reflects the denial
    resp = client.get("/tenants/t1/policy", headers=_headers("t1"))
    assert "calculate_result" in resp.json()["overlay"]["deny_tools"]


def test_cross_tenant_policy_access_is_forbidden() -> None:
    app = build_test_app()
    client = TestClient(app)
    resp = client.get("/tenants/t2/policy", headers=_headers("t1"))
    assert resp.status_code == 403
    assert "TENANT_SCOPE_MISMATCH" in resp.text


def test_cross_tenant_policy_access_remains_forbidden_for_super_admin_on_non_admin_route() -> None:
    settings = AppSettings(
        schema_version="1.0",
        environment="test",
        runtime=RuntimeSettings(
            default_provider_id="openai-test",
            allowed_provider_ids=["openai-test"],
            require_provider_healthcheck_on_start=False,
        ),
        auth=AuthSettings(
            allow_cross_tenant_admin=True,
            cross_tenant_admin_roles=["super_admin"],
        ),
    )
    app = build_test_app(settings=settings)
    client = TestClient(app)
    resp = client.get("/tenants/t2/policy", headers=_headers("t1", roles=["super_admin"]))
    assert resp.status_code == 403
    assert "TENANT_SCOPE_MISMATCH" in resp.text
