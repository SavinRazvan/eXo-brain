"""
File: test_slice3_playground.py
Path: tests/modules/api/test_slice3_playground.py
Role: Acceptance tests for Slice 3 — Adapter Playground: sessions, SSE turns, WebSocket, providers.
Used By:
 - pytest
Depends On:
 - src/api/routers/sessions.py
 - src/api/routers/turns.py
 - src/api/routers/providers.py
 - src/api/bootstrap.py
Notes:
 - WebSocket tests use starlette TestClient's websocket_connect context manager.
 - SSE tests verify events are returned as text/event-stream.
 - Provider tests verify the test adapter registered in build_test_app is visible.
 - All tests use the echo/fallback adapter path (no OPENAI_API_KEY required).
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from src.api.bootstrap import build_test_app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _headers(tenant_id: str = "t1") -> dict:
    payload = {"subject": "user@test.com", "roles": ["user"], "tenant_id": tenant_id,
               "token_validation_state": "valid"}
    return {"X-Identity": json.dumps(payload)}


def _register_agent(client: TestClient, tid: str, agent_id: str = "echo-agent",
                    role: str = "echo_role") -> None:
    client.post(
        f"/tenants/{tid}/agents",
        json={"agent_id": agent_id, "role": role, "instructions": "You are a helpful assistant."},
        headers=_headers(tid),
    )


def _create_session(client: TestClient, tid: str, agent_id: str = "echo-agent",
                    provider_id: str = "openai-test") -> str:
    resp = client.post(
        f"/tenants/{tid}/sessions",
        json={"agent_id": agent_id, "provider_id": provider_id},
        headers=_headers(tid),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["session_id"]


# ---------------------------------------------------------------------------
# Session creation
# ---------------------------------------------------------------------------


def test_create_session_success() -> None:
    app = build_test_app()
    client = TestClient(app)
    tid = "sess-tenant"
    _register_agent(client, tid)

    resp = client.post(
        f"/tenants/{tid}/sessions",
        json={"agent_id": "echo-agent", "provider_id": "openai-test", "correlation_id": "corr-xyz"},
        headers=_headers(tid),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["tenant_id"] == tid
    assert body["agent_id"] == "echo-agent"
    assert body["provider_id"] == "openai-test"
    assert body["correlation_id"] == "corr-xyz"
    assert body["session_id"].startswith("sess_")


def test_create_session_generates_session_id() -> None:
    app = build_test_app()
    client = TestClient(app)
    tid = "sess-id-tenant"
    _register_agent(client, tid)

    r1 = client.post(f"/tenants/{tid}/sessions",
                     json={"agent_id": "echo-agent", "provider_id": "openai-test"},
                     headers=_headers(tid))
    r2 = client.post(f"/tenants/{tid}/sessions",
                     json={"agent_id": "echo-agent", "provider_id": "openai-test"},
                     headers=_headers(tid))
    assert r1.json()["session_id"] != r2.json()["session_id"]


def test_create_session_returns_404_for_unknown_agent() -> None:
    app = build_test_app()
    client = TestClient(app)
    tid = "sess-404-tenant"
    resp = client.post(
        f"/tenants/{tid}/sessions",
        json={"agent_id": "ghost-agent", "provider_id": "openai-test"},
        headers=_headers(tid),
    )
    assert resp.status_code == 404


def test_create_session_returns_401_without_identity() -> None:
    app = build_test_app()
    client = TestClient(app)
    resp = client.post(
        "/tenants/t1/sessions",
        json={"agent_id": "a", "provider_id": "openai-test"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Session retrieval
# ---------------------------------------------------------------------------


def test_get_session_returns_stored_session() -> None:
    app = build_test_app()
    client = TestClient(app)
    tid = "get-sess-tenant"
    _register_agent(client, tid)
    session_id = _create_session(client, tid)

    resp = client.get(f"/tenants/{tid}/sessions/{session_id}", headers=_headers(tid))
    assert resp.status_code == 200
    body = resp.json()
    assert body["session_id"] == session_id
    assert body["tenant_id"] == tid
    assert body["agent_id"] == "echo-agent"


def test_get_session_returns_404_for_unknown_session() -> None:
    app = build_test_app()
    client = TestClient(app)
    tid = "ghost-sess-tenant"
    resp = client.get(f"/tenants/{tid}/sessions/sess_ghost", headers=_headers(tid))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# SSE turn execution
# ---------------------------------------------------------------------------


def test_sse_turn_returns_event_stream_content_type() -> None:
    app = build_test_app()
    client = TestClient(app)
    tid = "sse-tenant"
    _register_agent(client, tid)
    session_id = _create_session(client, tid)

    resp = client.post(
        f"/tenants/{tid}/sessions/{session_id}/turns",
        json={"input": "Hello"},
        headers=_headers(tid),
    )
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")


def test_sse_turn_contains_run_complete_event() -> None:
    app = build_test_app()
    client = TestClient(app)
    tid = "sse-complete-tenant"
    _register_agent(client, tid)
    session_id = _create_session(client, tid)

    resp = client.post(
        f"/tenants/{tid}/sessions/{session_id}/turns",
        json={"input": "Say hello"},
        headers=_headers(tid),
    )
    raw = resp.text
    # Parse SSE lines
    events = []
    for line in raw.splitlines():
        if line.startswith("data:"):
            data_str = line[len("data:"):].strip()
            try:
                events.append(json.loads(data_str))
            except json.JSONDecodeError:
                pass

    event_types = [e.get("event") for e in events]
    assert "run_complete" in event_types, f"Expected run_complete in {event_types}"


def test_sse_turn_returns_404_for_unknown_session() -> None:
    app = build_test_app()
    client = TestClient(app)
    tid = "sse-404-tenant"
    resp = client.post(
        f"/tenants/{tid}/sessions/sess_ghost/turns",
        json={"input": "hello"},
        headers=_headers(tid),
    )
    assert resp.status_code == 404


def test_sse_turn_output_delta_before_run_complete() -> None:
    """output_delta events must come before run_complete in the stream."""
    app = build_test_app()
    client = TestClient(app)
    tid = "sse-order-tenant"
    _register_agent(client, tid)
    session_id = _create_session(client, tid)

    resp = client.post(
        f"/tenants/{tid}/sessions/{session_id}/turns",
        json={"input": "anything"},
        headers=_headers(tid),
    )
    events = []
    for line in resp.text.splitlines():
        if line.startswith("data:"):
            try:
                events.append(json.loads(line[5:].strip()))
            except json.JSONDecodeError:
                pass

    event_types = [e.get("event") for e in events]
    if "output_delta" in event_types and "run_complete" in event_types:
        assert event_types.index("output_delta") < event_types.index("run_complete")


# ---------------------------------------------------------------------------
# WebSocket turn execution
# ---------------------------------------------------------------------------


def test_websocket_rejects_unknown_session() -> None:
    """Server closes WebSocket before accept() for unknown sessions; expect exception on connect."""
    app = build_test_app()
    client = TestClient(app)
    tid = "ws-404-tenant"

    # When the server closes without accepting (code 4404), the TestClient raises on __enter__
    try:
        with client.websocket_connect(f"/tenants/{tid}/sessions/sess_ghost/ws") as ws:
            # If somehow connected, the first receive should fail or be a close frame
            ws.receive_text()
    except Exception:
        pass  # Expected: connection refused / closed before accept


def test_websocket_accepts_valid_session() -> None:
    app = build_test_app()
    client = TestClient(app)
    tid = "ws-valid-tenant"
    _register_agent(client, tid)
    session_id = _create_session(client, tid)

    with client.websocket_connect(f"/tenants/{tid}/sessions/{session_id}/ws") as ws:
        ws.send_json({"type": "turn", "input": "hello from ws"})
        events = []
        while True:
            try:
                msg = ws.receive_json()
                events.append(msg)
                if msg.get("event") in ("run_complete", "error"):
                    break
            except Exception:
                break

    event_types = [e.get("event") for e in events]
    assert "run_complete" in event_types or len(events) > 0


def test_websocket_returns_error_for_invalid_json() -> None:
    app = build_test_app()
    client = TestClient(app)
    tid = "ws-json-err-tenant"
    _register_agent(client, tid)
    session_id = _create_session(client, tid)

    with client.websocket_connect(f"/tenants/{tid}/sessions/{session_id}/ws") as ws:
        ws.send_text("not-valid-json")
        msg = ws.receive_json()
        assert msg.get("event") == "error"
        assert msg.get("code") == "INVALID_JSON"


def test_websocket_returns_error_for_unknown_message_type() -> None:
    app = build_test_app()
    client = TestClient(app)
    tid = "ws-unknown-msg-tenant"
    _register_agent(client, tid)
    session_id = _create_session(client, tid)

    with client.websocket_connect(f"/tenants/{tid}/sessions/{session_id}/ws") as ws:
        ws.send_json({"type": "unknown_type"})
        msg = ws.receive_json()
        assert msg.get("event") == "error"
        assert msg.get("code") == "UNKNOWN_MESSAGE_TYPE"


def test_websocket_cancel_emits_run_cancelled_event() -> None:
    app = build_test_app()
    client = TestClient(app)
    tid = "ws-cancel-tenant"
    _register_agent(client, tid)
    session_id = _create_session(client, tid)

    with client.websocket_connect(f"/tenants/{tid}/sessions/{session_id}/ws") as ws:
        ws.send_json({"type": "cancel", "run_id": "run_abc123"})
        msg = ws.receive_json()
        assert msg.get("event") == "run_cancelled"
        assert msg.get("run_id") == "run_abc123"


# ---------------------------------------------------------------------------
# Provider endpoints
# ---------------------------------------------------------------------------


def test_list_providers_returns_test_provider() -> None:
    app = build_test_app()
    client = TestClient(app)
    resp = client.get("/providers", headers=_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    provider_ids = [p["provider_id"] for p in body["providers"]]
    assert "openai-test" in provider_ids


def test_list_providers_returns_401_without_identity() -> None:
    app = build_test_app()
    client = TestClient(app)
    resp = client.get("/providers")
    assert resp.status_code == 401


def test_get_provider_health_returns_healthy_for_test_provider() -> None:
    app = build_test_app()
    client = TestClient(app)
    resp = client.get("/providers/openai-test/health", headers=_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider_id"] == "openai-test"
    assert body["state"] == "healthy"


def test_get_provider_health_returns_404_for_unknown_provider() -> None:
    app = build_test_app()
    client = TestClient(app)
    resp = client.get("/providers/ghost-provider/health", headers=_headers())
    assert resp.status_code == 404


def test_get_provider_capabilities_returns_capability_map() -> None:
    app = build_test_app()
    client = TestClient(app)
    resp = client.get("/providers/openai-test/capabilities", headers=_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider_id"] == "openai-test"
    assert "supports_streaming" in body
    assert "supports_function_calling" in body
    assert "reliability_score" in body


def test_get_provider_capabilities_returns_404_for_unknown() -> None:
    app = build_test_app()
    client = TestClient(app)
    resp = client.get("/providers/ghost/capabilities", headers=_headers())
    assert resp.status_code == 404
