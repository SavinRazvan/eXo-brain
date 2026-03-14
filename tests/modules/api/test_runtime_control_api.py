"""
File: test_runtime_control_api.py
Path: tests/modules/api/test_runtime_control_api.py
Role: Acceptance tests for internal hosted runtime control endpoints.
Used By:
 - pytest
Depends On:
 - src/api/bootstrap.py
 - src/config/settings.py
Notes:
 - Uses X-Identity test auth to exercise internal runtime control APIs.
"""

from __future__ import annotations

import asyncio
import json

from fastapi.testclient import TestClient

from src.api.bootstrap import build_test_app
from src.config.settings import AppSettings, AuthSettings, RuntimeSettings


def _headers(tenant_id: str = "t1", roles: list[str] | None = None) -> dict[str, str]:
    payload = {
        "subject": "admin@test.com",
        "roles": roles or ["admin", "entitlement_pro"],
        "tenant_id": tenant_id,
        "token_validation_state": "valid",
    }
    return {"X-Identity": json.dumps(payload)}


def _hosted_control_client() -> TestClient:
    settings = AppSettings(
        schema_version="1.0",
        environment="test",
        runtime=RuntimeSettings(
            default_provider_id="openai-test",
            allowed_provider_ids=["openai-test"],
            require_provider_healthcheck_on_start=False,
            enable_hosted_tool_runtime=True,
        ),
    )
    return TestClient(build_test_app(settings=settings))


def test_runtime_control_stats_returns_hosted_adapter_metrics() -> None:
    client = _hosted_control_client()
    resp = client.get("/tenants/t1/admin/runtime/control-stats", headers=_headers("t1"))
    assert resp.status_code == 200
    body = resp.json()
    assert body["tenant_id"] == "t1"
    assert body["backend_id"] == "hosted_sandbox_runtime"
    assert "control_stats" in body
    assert "pool_stats" in body


def test_runtime_cleanup_events_endpoint_returns_list() -> None:
    client = _hosted_control_client()
    resp = client.get("/tenants/t1/admin/runtime/cleanup-events?limit=10", headers=_headers("t1"))
    assert resp.status_code == 200
    body = resp.json()
    assert body["tenant_id"] == "t1"
    assert body["backend_id"] == "hosted_sandbox_runtime"
    assert isinstance(body["events"], list)


def test_runtime_cancellation_create_and_clear_updates_pending_count() -> None:
    client = _hosted_control_client()
    create = client.post(
        "/tenants/t1/admin/runtime/cancellations",
        json={"call_id": "call-ctrl-1"},
        headers=_headers("t1"),
    )
    assert create.status_code == 200
    create_body = create.json()
    assert create_body["accepted"] is True
    assert create_body["pending_cancellations"] == 1

    clear = client.delete("/tenants/t1/admin/runtime/cancellations/call-ctrl-1", headers=_headers("t1"))
    assert clear.status_code == 200
    clear_body = clear.json()
    assert clear_body["accepted"] is True
    assert clear_body["pending_cancellations"] == 0


def test_runtime_control_endpoints_return_409_when_hosted_runtime_disabled() -> None:
    client = TestClient(build_test_app())
    resp = client.get("/tenants/t1/admin/runtime/control-stats", headers=_headers("t1"))
    assert resp.status_code == 409


def test_runtime_control_endpoints_require_authentication() -> None:
    client = _hosted_control_client()
    resp = client.get("/tenants/t1/admin/runtime/control-stats")
    assert resp.status_code == 401


def test_runtime_control_requires_pro_entitlement_and_emits_decision_audit() -> None:
    client = _hosted_control_client()
    app = client.app
    resp = client.get(
        "/tenants/t1/admin/runtime/control-stats",
        headers=_headers("t1", roles=["admin"]),
    )
    assert resp.status_code == 403
    assert "ENTITLEMENT_TIER_REQUIRED" in resp.text

    records = asyncio.run(app.state.audit_store.list_audit_events(tenant_id="t1", limit=20))
    entitlement = [record for record in records if record.event_type == "entitlement_decision"]
    assert entitlement
    latest = entitlement[-1]
    assert latest.payload.get("surface") == "runtime_control_admin"
    assert latest.payload.get("feature") == "governance.runtime.admin_controls"
    assert latest.payload.get("decision") == "deny"
    assert latest.payload.get("required_tier") == "pro"
    assert latest.payload.get("current_tier") == "foundation"


def test_runtime_run_list_and_get_expose_canonical_run_registry_state() -> None:
    client = _hosted_control_client()
    app = client.app
    registry = app.state.run_control_registry
    registry.start_run(
        tenant_id="t1",
        session_id="sess_1",
        run_id="run_registry_1",
        correlation_id="corr_registry_1",
        transport="websocket",
    )
    registry.record_tool_call(tenant_id="t1", run_id="run_registry_1", call_id="call_registry_1")
    registry.mark_terminal(
        tenant_id="t1",
        run_id="run_registry_1",
        status="completed",
        terminal_event="run_complete",
    )

    listed = client.get("/tenants/t1/admin/runtime/runs?limit=10", headers=_headers("t1"))
    assert listed.status_code == 200
    list_body = listed.json()
    assert list_body["total"] >= 1
    assert any(run["run_id"] == "run_registry_1" for run in list_body["runs"])

    fetched = client.get("/tenants/t1/admin/runtime/runs/run_registry_1", headers=_headers("t1"))
    assert fetched.status_code == 200
    run_body = fetched.json()
    assert run_body["run_id"] == "run_registry_1"
    assert run_body["status"] == "completed"
    assert run_body["call_ids"] == ["call_registry_1"]


def test_runtime_run_cancel_endpoint_forwards_call_cancellations() -> None:
    client = _hosted_control_client()
    app = client.app
    registry = app.state.run_control_registry
    registry.start_run(
        tenant_id="t1",
        session_id="sess_cancel",
        run_id="run_cancel_1",
        correlation_id="run_cancel_1",
        transport="websocket",
    )
    registry.record_tool_call(tenant_id="t1", run_id="run_cancel_1", call_id="call_cancel_1")

    resp = client.post("/tenants/t1/admin/runtime/runs/run_cancel_1/cancel", headers=_headers("t1"))
    assert resp.status_code == 200
    body = resp.json()
    assert body["accepted"] is True
    assert body["forwarded_call_cancellations"] >= 1

    run = client.get("/tenants/t1/admin/runtime/runs/run_cancel_1", headers=_headers("t1"))
    assert run.status_code == 200
    run_body = run.json()
    assert run_body["cancel_requested"] is True


def test_runtime_run_get_returns_404_for_unknown_run() -> None:
    client = _hosted_control_client()
    resp = client.get("/tenants/t1/admin/runtime/runs/run_missing", headers=_headers("t1"))
    assert resp.status_code == 404


def test_cross_tenant_admin_runtime_route_allows_configured_super_admin_bypass() -> None:
    settings = AppSettings(
        schema_version="1.0",
        environment="test",
        runtime=RuntimeSettings(
            default_provider_id="openai-test",
            allowed_provider_ids=["openai-test"],
            require_provider_healthcheck_on_start=False,
            enable_hosted_tool_runtime=True,
        ),
        auth=AuthSettings(
            allow_cross_tenant_admin=True,
            cross_tenant_admin_roles=["super_admin"],
        ),
    )
    app = build_test_app(settings=settings)
    client = TestClient(app)
    resp = client.get(
        "/tenants/t2/admin/runtime/control-stats",
        headers={
            "X-Identity": json.dumps(
                {
                    "subject": "sa@test.com",
                    "roles": ["super_admin", "entitlement_pro"],
                    "tenant_id": "t1",
                    "token_validation_state": "valid",
                }
            )
        },
    )
    assert resp.status_code == 200
    assert resp.json()["tenant_id"] == "t2"
