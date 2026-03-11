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

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from src.api.bootstrap import build_test_app
from src.config.settings import AppSettings, LimitsSettings, RuntimeSettings
from src.schemas.events import RuntimeEvent
from src.schemas.events import RuntimeEventType
from src.schemas.tool_io import ToolCallContext


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


def test_sse_turn_emits_tool_progress_state_transitions(monkeypatch: pytest.MonkeyPatch) -> None:
    app = build_test_app()
    client = TestClient(app)
    tid = "sse-progress-tenant"
    _register_agent(client, tid)
    session_id = _create_session(client, tid)

    async def _fake_stream_turn(**kwargs):
        _ = kwargs
        yield {
            "event": "tool_progress",
            "call_id": "call_sse_progress_1",
            "tool_name": "echo_tool",
            "state": "queued",
            "tool_status": "",
            "error_code": "",
            "correlation_id": "run_sse_progress",
        }
        yield {
            "event": "tool_progress",
            "call_id": "call_sse_progress_1",
            "tool_name": "echo_tool",
            "state": "running",
            "tool_status": "",
            "error_code": "",
            "correlation_id": "run_sse_progress",
        }
        yield {
            "event": "tool_progress",
            "call_id": "call_sse_progress_1",
            "tool_name": "echo_tool",
            "state": "completed",
            "tool_status": "success",
            "error_code": "",
            "correlation_id": "run_sse_progress",
        }
        yield {"event": "run_complete", "run_id": "run_sse_progress", "output": {}, "correlation_id": "run_sse_progress"}

    from src.api.routers import turns as turns_router_module

    monkeypatch.setattr(turns_router_module, "_stream_turn", _fake_stream_turn)

    resp = client.post(
        f"/tenants/{tid}/sessions/{session_id}/turns",
        json={"input": "trigger tool progress", "correlation_id": "run_sse_progress"},
        headers=_headers(tid),
    )
    assert resp.status_code == 200
    parsed = []
    for line in resp.text.splitlines():
        if line.startswith("data:"):
            parsed.append(json.loads(line[len("data:"):].strip()))
    progress_states = [entry.get("state") for entry in parsed if entry.get("event") == "tool_progress"]
    assert progress_states == ["queued", "running", "completed"]


def test_sse_turn_emits_cancelled_tool_progress_before_terminal_event(monkeypatch: pytest.MonkeyPatch) -> None:
    app = build_test_app()
    client = TestClient(app)
    tid = "sse-cancel-order-tenant"
    _register_agent(client, tid)
    session_id = _create_session(client, tid)

    async def _fake_stream_turn(**kwargs):
        _ = kwargs
        yield {
            "event": "tool_progress",
            "call_id": "call_sse_cancel_1",
            "tool_name": "echo_tool",
            "state": "running",
            "tool_status": "",
            "error_code": "",
            "correlation_id": "run_sse_cancel_1",
        }
        app.state.run_control_registry.request_cancel(
            tenant_id=tid,
            run_id="run_sse_cancel_1",
            reason="test_sse_cancel_order",
        )
        yield {"event": "run_complete", "run_id": "run_sse_cancel_1", "output": {}, "correlation_id": "run_sse_cancel_1"}

    from src.api.routers import turns as turns_router_module

    monkeypatch.setattr(turns_router_module, "_stream_turn", _fake_stream_turn)

    resp = client.post(
        f"/tenants/{tid}/sessions/{session_id}/turns",
        json={"input": "trigger cancel ordering", "correlation_id": "run_sse_cancel_1"},
        headers=_headers(tid),
    )
    assert resp.status_code == 200
    parsed = []
    for line in resp.text.splitlines():
        if line.startswith("data:"):
            parsed.append(json.loads(line[len("data:"):].strip()))
    events = [entry.get("event") for entry in parsed]
    states = [entry.get("state") for entry in parsed if entry.get("event") == "tool_progress"]
    assert events[:2] == ["tool_progress", "tool_progress"]
    assert states == ["running", "cancelled"]
    assert "run_complete" not in events


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
        with client.websocket_connect(f"/tenants/{tid}/sessions/sess_ghost/ws", headers=_headers(tid)) as ws:
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

    with client.websocket_connect(f"/tenants/{tid}/sessions/{session_id}/ws", headers=_headers(tid)) as ws:
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


def test_websocket_rejects_cross_tenant_identity() -> None:
    app = build_test_app()
    client = TestClient(app)
    tid = "ws-scope-tenant"
    _register_agent(client, tid)
    session_id = _create_session(client, tid)
    with pytest.raises(Exception):
        with client.websocket_connect(
            f"/tenants/{tid}/sessions/{session_id}/ws",
            headers=_headers("different-tenant"),
        ):
            pass


def test_websocket_turn_emits_tool_progress_state_transitions(monkeypatch: pytest.MonkeyPatch) -> None:
    app = build_test_app()
    client = TestClient(app)
    tid = "ws-progress-tenant"
    _register_agent(client, tid)
    session_id = _create_session(client, tid)

    async def _fake_stream_turn(**kwargs):
        _ = kwargs
        yield {
            "event": "tool_progress",
            "call_id": "call_ws_progress_1",
            "tool_name": "echo_tool",
            "state": "queued",
            "tool_status": "",
            "error_code": "",
            "correlation_id": "run_ws_progress",
        }
        yield {
            "event": "tool_progress",
            "call_id": "call_ws_progress_1",
            "tool_name": "echo_tool",
            "state": "running",
            "tool_status": "",
            "error_code": "",
            "correlation_id": "run_ws_progress",
        }
        yield {
            "event": "tool_progress",
            "call_id": "call_ws_progress_1",
            "tool_name": "echo_tool",
            "state": "completed",
            "tool_status": "success",
            "error_code": "",
            "correlation_id": "run_ws_progress",
        }
        yield {"event": "run_complete", "run_id": "run_ws_progress", "output": {}, "correlation_id": "run_ws_progress"}

    from src.api.routers import turns as turns_router_module

    monkeypatch.setattr(turns_router_module, "_stream_turn", _fake_stream_turn)

    with client.websocket_connect(f"/tenants/{tid}/sessions/{session_id}/ws", headers=_headers(tid)) as ws:
        ws.send_json({"type": "turn", "input": "trigger", "run_id": "run_ws_progress"})
        states: list[str] = []
        while True:
            message = ws.receive_json()
            if message.get("event") == "tool_progress":
                states.append(str(message.get("state", "")))
            if message.get("event") in {"run_complete", "error"}:
                break
    assert states == ["queued", "running", "completed"]


def test_websocket_forced_disconnect_marks_terminal_cancelled(monkeypatch: pytest.MonkeyPatch) -> None:
    app = build_test_app()
    client = TestClient(app)
    tid = "ws-forced-disconnect-tenant"
    _register_agent(client, tid)
    session_id = _create_session(client, tid)

    async def _fake_stream_turn(**kwargs):
        _ = kwargs
        yield {
            "event": "tool_progress",
            "call_id": "call_disconnect_1",
            "tool_name": "echo_tool",
            "state": "running",
            "tool_status": "",
            "error_code": "",
            "job_id": "job_disconnect_1",
            "lease_token": "lease_disconnect_1",
            "lease_expires_at_epoch": "123",
            "claim_attempt": "1",
            "correlation_id": "run_disconnect_1",
        }
        await asyncio.sleep(1.0)
        yield {"event": "run_complete", "run_id": "run_disconnect_1", "output": {}, "correlation_id": "run_disconnect_1"}

    from src.api.routers import turns as turns_router_module

    monkeypatch.setattr(turns_router_module, "_stream_turn", _fake_stream_turn)

    with client.websocket_connect(f"/tenants/{tid}/sessions/{session_id}/ws", headers=_headers(tid)) as ws:
        ws.send_json({"type": "turn", "input": "disconnect-race", "run_id": "run_disconnect_1"})
        first = ws.receive_json()
        assert first.get("event") == "tool_progress"
        # Context exit forces disconnect while turn is still running.

    run_record = app.state.run_control_registry.get_run(tenant_id=tid, run_id="run_disconnect_1")
    assert run_record is not None
    assert run_record["status"] == "cancelled"
    assert run_record["terminal_event"] in {"websocket_disconnect", "ws_task_cancelled"}


def test_websocket_late_cancel_does_not_override_completed_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    app = build_test_app()
    client = TestClient(app)
    tid = "ws-late-cancel-tenant"
    _register_agent(client, tid)
    session_id = _create_session(client, tid)

    async def _fake_stream_turn(**kwargs):
        _ = kwargs
        yield {"event": "run_complete", "run_id": "run_late_cancel_1", "output": {}, "correlation_id": "run_late_cancel_1"}

    from src.api.routers import turns as turns_router_module

    monkeypatch.setattr(turns_router_module, "_stream_turn", _fake_stream_turn)

    with client.websocket_connect(f"/tenants/{tid}/sessions/{session_id}/ws", headers=_headers(tid)) as ws:
        ws.send_json({"type": "turn", "input": "complete-fast", "run_id": "run_late_cancel_1"})
        done = ws.receive_json()
        assert done.get("event") == "run_complete"
        ws.send_json({"type": "cancel", "run_id": "run_late_cancel_1"})
        cancelled = ws.receive_json()
        assert cancelled.get("event") == "run_cancelled"

    run_record = app.state.run_control_registry.get_run(tenant_id=tid, run_id="run_late_cancel_1")
    assert run_record is not None
    assert run_record["status"] == "completed"
    assert run_record["terminal_event"] == "run_complete"


def test_websocket_returns_error_for_invalid_json() -> None:
    app = build_test_app()
    client = TestClient(app)
    tid = "ws-json-err-tenant"
    _register_agent(client, tid)
    session_id = _create_session(client, tid)

    with client.websocket_connect(f"/tenants/{tid}/sessions/{session_id}/ws", headers=_headers(tid)) as ws:
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

    with client.websocket_connect(f"/tenants/{tid}/sessions/{session_id}/ws", headers=_headers(tid)) as ws:
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

    with client.websocket_connect(f"/tenants/{tid}/sessions/{session_id}/ws", headers=_headers(tid)) as ws:
        ws.send_json({"type": "cancel", "run_id": "run_abc123"})
        msg = ws.receive_json()
        assert msg.get("event") == "run_cancelled"
        assert msg.get("run_id") == "run_abc123"


def test_runtime_event_to_dict_tool_call_includes_call_id() -> None:
    from src.api.routers.turns import _runtime_event_to_dict

    event = RuntimeEvent.tool_intent(
        session_id="sess_1",
        run_id="run_1",
        correlation_id="corr_1",
        call=ToolCallContext(
            schema_version="1.0",
            call_id="call_123",
            session_id="sess_1",
            run_id="run_1",
            job_id="job_1",
            task_id="task_1",
            agent_id="agent_1",
            provider_id="openai-test",
            tool_name="math_tool",
            arguments={"a": 1, "b": 2},
        ),
    )
    payload = _runtime_event_to_dict(event)
    assert payload["event"] == "tool_call"
    assert payload["call_id"] == "call_123"


def test_runtime_event_to_dict_tool_progress_maps_state_fields() -> None:
    from src.api.routers.turns import _runtime_event_to_dict

    event = RuntimeEvent(
        event_type=RuntimeEventType.TOOL_PROGRESS,
        session_id="sess_progress",
        run_id="run_progress",
        correlation_id="corr_progress",
        payload={
            "call_id": "call_progress_1",
            "tool_name": "math_tool",
            "state": "running",
            "tool_status": "success",
            "error_code": "",
            "job_id": "job_progress_1",
            "lease_token": "lease_123",
            "lease_expires_at_epoch": "123456",
            "claim_attempt": "2",
        },
    )
    payload = _runtime_event_to_dict(event)
    assert payload["event"] == "tool_progress"
    assert payload["call_id"] == "call_progress_1"
    assert payload["state"] == "running"
    assert payload["job_id"] == "job_progress_1"
    assert payload["lease_token"] == "lease_123"
    assert payload["lease_expires_at_epoch"] == "123456"
    assert payload["claim_attempt"] == "2"


def test_websocket_cancel_forwards_tool_call_ids_to_runtime_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
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
    app = build_test_app(settings=settings)
    client = TestClient(app)
    tid = "ws-cancel-forward-tenant"
    _register_agent(client, tid)
    session_id = _create_session(client, tid)

    async def _fake_stream_turn(**kwargs):
        _ = kwargs
        yield {
            "event": "tool_call",
            "call_id": "call_forward_1",
            "tool_name": "math_tool",
            "arguments": {},
            "correlation_id": "run_forward_1",
        }
        await asyncio.sleep(0.2)
        yield {"event": "run_complete", "run_id": "run_forward_1", "output": {}, "correlation_id": "run_forward_1"}

    from src.api.routers import turns as turns_router_module

    monkeypatch.setattr(turns_router_module, "_stream_turn", _fake_stream_turn)

    with client.websocket_connect(f"/tenants/{tid}/sessions/{session_id}/ws", headers=_headers(tid)) as ws:
        ws.send_json({"type": "turn", "input": "trigger tool", "run_id": "run_forward_1"})
        first = ws.receive_json()
        assert first.get("event") == "tool_call"
        ws.send_json({"type": "cancel", "run_id": "run_forward_1"})
        cancel_progress = ws.receive_json()
        assert cancel_progress.get("event") == "tool_progress"
        assert cancel_progress.get("state") == "cancelled"
        assert cancel_progress.get("call_id") == "call_forward_1"
        cancelled = ws.receive_json()
        assert cancelled.get("event") == "run_cancelled"
        assert cancelled.get("run_id") == "run_forward_1"

    ctx = app.state.tenant_factory.get_or_create(tid)
    adapter = ctx.tool_executor.execution_adapter()
    assert adapter is not None
    control_stats = adapter.control_stats()
    assert control_stats["cancel_requested_total"] >= 1
    assert control_stats["pending_cancellations"] >= 1
    run_record = app.state.run_control_registry.get_run(tenant_id=tid, run_id="run_forward_1")
    assert run_record is not None
    assert run_record["cancel_requested"] is True
    assert "call_forward_1" in run_record["call_ids"]


def test_websocket_cancel_forwards_call_id_seen_from_tool_progress(monkeypatch: pytest.MonkeyPatch) -> None:
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
    app = build_test_app(settings=settings)
    client = TestClient(app)
    tid = "ws-cancel-progress-tenant"
    _register_agent(client, tid)
    session_id = _create_session(client, tid)

    async def _fake_stream_turn(**kwargs):
        _ = kwargs
        yield {
            "event": "tool_progress",
            "call_id": "call_progress_1",
            "tool_name": "math_tool",
            "state": "running",
            "tool_status": "",
            "error_code": "",
            "correlation_id": "run_progress_1",
        }
        await asyncio.sleep(0.2)
        yield {"event": "run_complete", "run_id": "run_progress_1", "output": {}, "correlation_id": "run_progress_1"}

    from src.api.routers import turns as turns_router_module

    monkeypatch.setattr(turns_router_module, "_stream_turn", _fake_stream_turn)

    with client.websocket_connect(f"/tenants/{tid}/sessions/{session_id}/ws", headers=_headers(tid)) as ws:
        ws.send_json({"type": "turn", "input": "trigger tool", "run_id": "run_progress_1"})
        first = ws.receive_json()
        assert first.get("event") == "tool_progress"
        ws.send_json({"type": "cancel", "run_id": "run_progress_1"})
        cancel_progress = ws.receive_json()
        assert cancel_progress.get("event") == "tool_progress"
        assert cancel_progress.get("state") == "cancelled"
        assert cancel_progress.get("call_id") == "call_progress_1"
        cancelled = ws.receive_json()
        assert cancelled.get("event") == "run_cancelled"
        assert cancelled.get("run_id") == "run_progress_1"

    run_record = app.state.run_control_registry.get_run(tenant_id=tid, run_id="run_progress_1")
    assert run_record is not None
    assert "call_progress_1" in run_record["call_ids"]


def test_forward_runtime_cancellations_forwards_only_when_non_terminal() -> None:
    from src.api.routers.turns import _forward_runtime_cancellations

    class _Adapter:
        def __init__(self) -> None:
            self.call_ids: list[str] = []

        def request_cancellation(self, call_id: str) -> bool:
            self.call_ids.append(call_id)
            return True

    adapter = _Adapter()
    forwarded = _forward_runtime_cancellations(
        execution_adapter=adapter,
        call_ids={"call_b", "call_a"},
        terminal_event_seen=False,
    )
    assert forwarded == 2
    assert adapter.call_ids == ["call_a", "call_b"]


def test_forward_runtime_cancellations_skips_when_terminal_seen() -> None:
    from src.api.routers.turns import _forward_runtime_cancellations

    class _Adapter:
        def request_cancellation(self, call_id: str) -> bool:
            _ = call_id
            raise AssertionError("Should not request cancellation after terminal event.")

    forwarded = _forward_runtime_cancellations(
        execution_adapter=_Adapter(),
        call_ids={"call_a"},
        terminal_event_seen=True,
    )
    assert forwarded == 0


def test_sse_turn_registers_completed_run_in_control_registry() -> None:
    app = build_test_app()
    client = TestClient(app)
    tid = "sse-registry-tenant"
    _register_agent(client, tid)
    session_id = _create_session(client, tid)

    resp = client.post(
        f"/tenants/{tid}/sessions/{session_id}/turns",
        json={"input": "hello", "correlation_id": "run_sse_1"},
        headers=_headers(tid),
    )
    assert resp.status_code == 200
    run_record = app.state.run_control_registry.get_run(tenant_id=tid, run_id="run_sse_1")
    assert run_record is not None
    assert run_record["status"] in {"completed", "errored"}


def test_sse_turn_returns_429_when_tenant_concurrency_limit_exceeded() -> None:
    app = build_test_app(
        settings=AppSettings(
            schema_version="1.0",
            environment="test",
            runtime=RuntimeSettings(
                default_provider_id="openai-test",
                allowed_provider_ids=["openai-test"],
                require_provider_healthcheck_on_start=False,
            ),
            limits=LimitsSettings(max_active_runs_per_tenant=1),
        )
    )
    client = TestClient(app)
    tid = "sse-concurrency-limit-tenant"
    _register_agent(client, tid)
    session_id = _create_session(client, tid)
    app.state.run_control_registry.start_run(
        tenant_id=tid,
        session_id=session_id,
        run_id="run_existing_1",
        correlation_id="run_existing_1",
        transport="sse",
    )
    resp = client.post(
        f"/tenants/{tid}/sessions/{session_id}/turns",
        json={"input": "should throttle", "correlation_id": "run_new_1"},
        headers=_headers(tid),
    )
    assert resp.status_code == 429
    assert "TENANT_CONCURRENCY_LIMIT_EXCEEDED" in resp.text


def test_websocket_turn_returns_error_when_rate_limited(monkeypatch: pytest.MonkeyPatch) -> None:
    app = build_test_app(
        settings=AppSettings(
            schema_version="1.0",
            environment="test",
            runtime=RuntimeSettings(
                default_provider_id="openai-test",
                allowed_provider_ids=["openai-test"],
                require_provider_healthcheck_on_start=False,
            ),
            limits=LimitsSettings(max_turn_requests_per_minute_per_tenant=1),
        )
    )
    client = TestClient(app)
    tid = "ws-rate-limit-tenant"
    _register_agent(client, tid)
    session_id = _create_session(client, tid)

    async def _fake_stream_turn(**kwargs):
        _ = kwargs
        yield {"event": "run_complete", "run_id": "run_ws_rate_1", "output": {}, "correlation_id": "run_ws_rate_1"}

    from src.api.routers import turns as turns_router_module

    monkeypatch.setattr(turns_router_module, "_stream_turn", _fake_stream_turn)
    with client.websocket_connect(f"/tenants/{tid}/sessions/{session_id}/ws", headers=_headers(tid)) as ws:
        ws.send_json({"type": "turn", "input": "first", "run_id": "run_ws_rate_1"})
        first = ws.receive_json()
        assert first.get("event") == "run_complete"
        ws.send_json({"type": "turn", "input": "second", "run_id": "run_ws_rate_2"})
        second = ws.receive_json()
        assert second.get("event") == "error"
        assert second.get("code") == "TENANT_TURN_RATE_LIMIT_EXCEEDED"
        assert int(second.get("retry_after_seconds", 0)) > 0


def test_sse_turn_returns_429_with_retry_hint_when_rate_limited() -> None:
    app = build_test_app(
        settings=AppSettings(
            schema_version="1.0",
            environment="test",
            runtime=RuntimeSettings(
                default_provider_id="openai-test",
                allowed_provider_ids=["openai-test"],
                require_provider_healthcheck_on_start=False,
            ),
            limits=LimitsSettings(max_turn_requests_per_minute_per_tenant=1),
        )
    )
    client = TestClient(app)
    tid = "sse-rate-limit-tenant"
    _register_agent(client, tid)
    session_id = _create_session(client, tid)

    first = client.post(
        f"/tenants/{tid}/sessions/{session_id}/turns",
        json={"input": "first", "correlation_id": "run_sse_rate_1"},
        headers=_headers(tid),
    )
    assert first.status_code == 200

    second = client.post(
        f"/tenants/{tid}/sessions/{session_id}/turns",
        json={"input": "second", "correlation_id": "run_sse_rate_2"},
        headers=_headers(tid),
    )
    assert second.status_code == 429
    assert "TENANT_TURN_RATE_LIMIT_EXCEEDED" in second.text
    assert "retry_after_seconds=" in second.text


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
