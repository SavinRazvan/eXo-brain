"""
File: test_turns_router_branches.py
Path: tests/modules/api/test_turns_router_branches.py
Role: Branch-focused coverage tests for turns SSE/WebSocket router helpers and edge paths.
Used By:
 - pytest
Depends On:
 - src/api/routers/turns.py
 - src/api/bootstrap.py
Notes:
 - Targets defensive/error branches not exercised by the primary slice3 playground suite.
"""

from __future__ import annotations

import asyncio
import json
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from src.api.bootstrap import build_test_app
from src.api.routers import turns as turns_router_module
from src.api.routers.turns import (
    _get_tenant_policy_overlay,
    _ingress_config_invalid_decision,
    _runtime_event_to_dict,
    _stream_turn,
    _websocket_cross_tenant_admin_allowed,
)
from src.config.settings import AppSettings, LimitsSettings, RuntimeSettings
from src.identity.contracts import IdentityContext
from src.observability.ingress_budget import IngressBudgetObservation
from src.policies.ingress_gates import IngressDecision
from src.schemas.events import RuntimeEvent, RuntimeEventType
from src.schemas.tool_io import PolicyAction


def _headers(tenant_id: str = "t1", roles: list[str] | None = None) -> dict[str, str]:
    payload = {
        "subject": "user@test.com",
        "roles": roles or ["user"],
        "tenant_id": tenant_id,
        "token_validation_state": "valid",
    }
    return {"X-Identity": json.dumps(payload)}


def _register_agent_and_session(client: TestClient, tenant_id: str) -> str:
    client.post(
        f"/tenants/{tenant_id}/agents",
        json={"agent_id": "echo-agent", "role": "echo_role", "instructions": "test"},
        headers=_headers(tenant_id),
    )
    resp = client.post(
        f"/tenants/{tenant_id}/sessions",
        json={"agent_id": "echo-agent", "provider_id": "openai-test"},
        headers=_headers(tenant_id),
    )
    assert resp.status_code == 201, resp.text
    return str(resp.json()["session_id"])


def test_turns_helpers_overlay_and_invalid_ingress_decision() -> None:
    app = SimpleNamespace(state=SimpleNamespace())
    assert _get_tenant_policy_overlay(app, "t1") == {}
    decision = _ingress_config_invalid_decision("bad ingress profile")
    assert decision.decision == PolicyAction.DENY
    assert decision.reason_code == "INGRESS_PROFILE_CONFIG_INVALID"
    assert "bad ingress profile" in decision.message


def test_runtime_event_to_dict_maps_error_and_fallback_payload() -> None:
    error_event = RuntimeEvent.error(
        session_id="s1",
        run_id="r1",
        code="FAIL",
        message="boom",
        correlation_id="corr_1",
    )
    error_payload = _runtime_event_to_dict(error_event)
    assert error_payload["event"] == "error"
    assert error_payload["code"] == "FAIL"

    fallback_event = SimpleNamespace(
        event_type=SimpleNamespace(value="custom_event"),
        payload={"k": "v"},
        correlation_id="corr_custom",
    )
    fallback_payload = _runtime_event_to_dict(fallback_event)
    assert fallback_payload["event"] == "custom_event"
    assert fallback_payload["payload"] == {"k": "v"}


@pytest.mark.asyncio
async def test_stream_turn_returns_error_for_missing_session() -> None:
    class _Factory:
        @staticmethod
        def get_session_runtime(session_id: str):
            _ = session_id
            raise KeyError("missing")

    identity = IdentityContext(subject="user", roles=["user"], tenant_id="t1", token_validation_state="valid")
    events = [
        event
        async for event in _stream_turn(
            tenant_id="t1",
            session_id="sess_missing",
            user_input="hello",
            correlation_id="corr_missing",
            ingress_decision=None,
            factory=_Factory(),
            ctx=SimpleNamespace(),
            identity=identity,
        )
    ]
    assert events[0]["event"] == "error"
    assert events[0]["code"] == "SESSION_NOT_FOUND"


@pytest.mark.asyncio
async def test_stream_turn_returns_error_when_adapter_submit_fails() -> None:
    class _HostAdapter:
        async def submit_turn(self, session_ctx, user_input):  # pragma: no cover - generator shape only
            _ = session_ctx
            _ = user_input
            raise RuntimeError("submit failed")
            yield  # pragma: no cover

    class _Factory:
        @staticmethod
        def get_session_runtime(session_id: str):
            _ = session_id
            return _HostAdapter()

    identity = IdentityContext(subject="user", roles=["user"], tenant_id="t1", token_validation_state="valid")
    events = [
        event
        async for event in _stream_turn(
            tenant_id="t1",
            session_id="sess_ok",
            user_input="hello",
            correlation_id="corr_fail",
            ingress_decision=None,
            factory=_Factory(),
            ctx=SimpleNamespace(),
            identity=identity,
        )
    ]
    assert events[0]["event"] == "error"
    assert events[0]["code"] == "TURN_EXECUTION_ERROR"
    assert "submit failed" in events[0]["message"]


def test_websocket_cross_tenant_admin_allowed_with_matching_role() -> None:
    websocket = SimpleNamespace(
        url=SimpleNamespace(path="/tenants/t1/admin/sessions/s1/ws"),
        app=SimpleNamespace(
            state=SimpleNamespace(
                settings=SimpleNamespace(
                    auth=SimpleNamespace(
                        allow_cross_tenant_admin=True,
                        cross_tenant_admin_roles=["super_admin", "admin"],
                    )
                )
            )
        ),
    )
    identity = IdentityContext(
        subject="admin@example.com",
        roles=["super_admin"],
        tenant_id="other",
        token_validation_state="valid",
    )
    assert _websocket_cross_tenant_admin_allowed(websocket, identity) is True


def test_websocket_cross_tenant_admin_denies_without_bypass_or_roles() -> None:
    identity = IdentityContext(
        subject="admin@example.com",
        roles=["super_admin"],
        tenant_id="other",
        token_validation_state="valid",
    )
    no_bypass_ws = SimpleNamespace(
        url=SimpleNamespace(path="/tenants/t1/admin/sessions/s1/ws"),
        app=SimpleNamespace(
            state=SimpleNamespace(
                settings=SimpleNamespace(
                    auth=SimpleNamespace(
                        allow_cross_tenant_admin=False,
                        cross_tenant_admin_roles=["super_admin"],
                    )
                )
            )
        ),
    )
    assert _websocket_cross_tenant_admin_allowed(no_bypass_ws, identity) is False

    empty_roles_ws = SimpleNamespace(
        url=SimpleNamespace(path="/tenants/t1/admin/sessions/s1/ws"),
        app=SimpleNamespace(
            state=SimpleNamespace(
                settings=SimpleNamespace(
                    auth=SimpleNamespace(
                        allow_cross_tenant_admin=True,
                        cross_tenant_admin_roles=["", "   "],
                    )
                )
            )
        ),
    )
    assert _websocket_cross_tenant_admin_allowed(empty_roles_ws, identity) is False


@pytest.mark.asyncio
async def test_evaluate_ingress_turn_defaults_profile_when_metadata_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    called: dict[str, str] = {}

    async def _fake_evaluate_with_budget(**kwargs):
        called["profile_name"] = str(kwargs["profile_name"])
        return (
            IngressDecision(
                schema_version="1.0",
                decision=PolicyAction.ALLOW,
                reason_code="INGRESS_ALLOW_DEFAULT",
                message="ok",
                gate_id="ingress-baseline",
                gate_version="1.0.0",
            ),
            IngressBudgetObservation(
                latency_ms=1.0,
                budget_ms=25,
                timeout_ms=50,
                timeout_fail_mode="fail_open",
                timed_out=False,
                budget_exceeded=False,
                reason_code="INGRESS_ALLOW_DEFAULT",
                decision="allow",
            ),
        )

    class _Gate:
        @staticmethod
        def policy_metadata() -> dict[str, str]:
            return {"ingress_profile": "   "}

        @staticmethod
        def evaluate(_ctx):
            return IngressDecision(
                schema_version="1.0",
                decision=PolicyAction.ALLOW,
                reason_code="INGRESS_ALLOW_DEFAULT",
                message="ok",
                gate_id="ingress-baseline",
                gate_version="1.0.0",
            )

    monkeypatch.setattr(turns_router_module, "evaluate_with_budget", _fake_evaluate_with_budget)
    decision = await turns_router_module._evaluate_ingress_turn(
        gate_chain=_Gate(),
        budget_config=turns_router_module.budget_config_from_policy_settings(
            build_test_app().state.settings.policy
        ),
        tenant_id="t1",
        session_id="s1",
        correlation_id="c1",
        transport="sse",
        user_input="hello",
        identity=IdentityContext(subject="u", roles=["user"], tenant_id="t1", token_validation_state="valid"),
        budget_recorder=None,
        audit_pipeline=None,
    )
    assert decision.decision == PolicyAction.ALLOW
    assert called["profile_name"] == turns_router_module.DEFAULT_INGRESS_PROFILE


def test_sse_returns_403_when_ingress_chain_build_fails() -> None:
    app = build_test_app()
    client = TestClient(app)
    tenant_id = "sse-ingress-build-fail"
    session_id = _register_agent_and_session(client, tenant_id)

    def _raise(_overlay):
        raise ValueError("invalid overlay")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(turns_router_module, "_build_ingress_gate_chain", _raise)
        resp = client.post(
            f"/tenants/{tenant_id}/sessions/{session_id}/turns",
            json={"input": "hello", "correlation_id": "run_sse_ingress_build_fail"},
            headers=_headers(tenant_id),
        )
    assert resp.status_code == 403
    assert "INGRESS_PROFILE_CONFIG_INVALID" in resp.text


def test_sse_marks_cancel_forwarded_when_stream_ends_without_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
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
    tenant_id = "sse-cancel-forward-tenant"
    session_id = _register_agent_and_session(client, tenant_id)
    run_id = "run_sse_cancel_forward_1"

    async def _fake_stream_turn(**kwargs):
        _ = kwargs
        yield {
            "event": "tool_call",
            "call_id": "call_sse_forward_1",
            "tool_name": "echo_tool",
            "arguments": {},
            "correlation_id": run_id,
        }

    monkeypatch.setattr(turns_router_module, "_stream_turn", _fake_stream_turn)
    ctx = app.state.tenant_factory.get_or_create(tenant_id)
    adapter = ctx.tool_executor.execution_adapter()
    assert adapter is not None
    monkeypatch.setattr(adapter, "request_cancellation", lambda call_id: str(call_id) == "call_sse_forward_1")

    resp = client.post(
        f"/tenants/{tenant_id}/sessions/{session_id}/turns",
        json={"input": "hello", "correlation_id": run_id},
        headers=_headers(tenant_id),
    )
    assert resp.status_code == 200
    record = app.state.run_control_registry.get_run(tenant_id=tenant_id, run_id=run_id)
    assert record is not None
    assert record["status"] == "cancelled"
    assert record["terminal_event"] == "cancel_forwarded"


def test_sse_marks_error_terminal_message_when_stream_emits_error(monkeypatch: pytest.MonkeyPatch) -> None:
    app = build_test_app()
    client = TestClient(app)
    tenant_id = "sse-error-terminal-tenant"
    session_id = _register_agent_and_session(client, tenant_id)
    run_id = "run_sse_error_terminal_1"

    async def _fake_stream_turn(**kwargs):
        _ = kwargs
        yield {"event": "error", "code": "X", "message": "boom from stream", "correlation_id": run_id}

    monkeypatch.setattr(turns_router_module, "_stream_turn", _fake_stream_turn)
    resp = client.post(
        f"/tenants/{tenant_id}/sessions/{session_id}/turns",
        json={"input": "hello", "correlation_id": run_id},
        headers=_headers(tenant_id),
    )
    assert resp.status_code == 200
    record = app.state.run_control_registry.get_run(tenant_id=tenant_id, run_id=run_id)
    assert record is not None
    assert record["status"] == "errored"
    assert record["terminal_message"] == "boom from stream"


def test_sse_marks_interrupted_when_stream_closes_without_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    app = build_test_app()
    client = TestClient(app)
    tenant_id = "sse-interrupted-tenant"
    session_id = _register_agent_and_session(client, tenant_id)
    run_id = "run_sse_interrupted_1"

    async def _fake_stream_turn(**kwargs):
        _ = kwargs
        yield {"event": "output_delta", "delta": "partial", "correlation_id": run_id}

    monkeypatch.setattr(turns_router_module, "_stream_turn", _fake_stream_turn)
    resp = client.post(
        f"/tenants/{tenant_id}/sessions/{session_id}/turns",
        json={"input": "hello", "correlation_id": run_id},
        headers=_headers(tenant_id),
    )
    assert resp.status_code == 200
    record = app.state.run_control_registry.get_run(tenant_id=tenant_id, run_id=run_id)
    assert record is not None
    assert record["status"] == "interrupted"
    assert record["terminal_event"] == "stream_closed"


def test_websocket_rejects_when_authentication_missing() -> None:
    app = build_test_app()
    client = TestClient(app)
    tenant_id = "ws-auth-missing-tenant"
    session_id = _register_agent_and_session(client, tenant_id)
    with pytest.raises(Exception):
        with client.websocket_connect(f"/tenants/{tenant_id}/sessions/{session_id}/ws"):
            pass


def test_websocket_turn_rejects_empty_input() -> None:
    app = build_test_app()
    client = TestClient(app)
    tenant_id = "ws-empty-input-tenant"
    session_id = _register_agent_and_session(client, tenant_id)
    with client.websocket_connect(f"/tenants/{tenant_id}/sessions/{session_id}/ws", headers=_headers(tenant_id)) as ws:
        ws.send_json({"type": "turn", "input": "   ", "run_id": "run_ws_empty"})
        msg = ws.receive_json()
        assert msg["event"] == "error"
        assert msg["code"] == "EMPTY_INPUT"


def test_websocket_turn_ingress_build_failure_returns_error_event(monkeypatch: pytest.MonkeyPatch) -> None:
    app = build_test_app()
    client = TestClient(app)
    tenant_id = "ws-ingress-build-fail-tenant"
    session_id = _register_agent_and_session(client, tenant_id)

    def _raise(_overlay):
        raise ValueError("bad overlay")

    monkeypatch.setattr(turns_router_module, "_build_ingress_gate_chain", _raise)
    with client.websocket_connect(f"/tenants/{tenant_id}/sessions/{session_id}/ws", headers=_headers(tenant_id)) as ws:
        ws.send_json({"type": "turn", "input": "hello", "run_id": "run_ws_ingress_build_fail"})
        msg = ws.receive_json()
        assert msg["event"] == "error"
        assert msg["code"] == "INGRESS_PROFILE_CONFIG_INVALID"


def test_websocket_turn_rejects_when_concurrency_limit_exceeded() -> None:
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
    tenant_id = "ws-concurrency-limit-tenant"
    session_id = _register_agent_and_session(client, tenant_id)
    app.state.run_control_registry.start_run(
        tenant_id=tenant_id,
        session_id=session_id,
        run_id="existing_run",
        correlation_id="existing_run",
        transport="websocket",
    )
    with client.websocket_connect(f"/tenants/{tenant_id}/sessions/{session_id}/ws", headers=_headers(tenant_id)) as ws:
        ws.send_json({"type": "turn", "input": "hello", "run_id": "run_ws_new"})
        msg = ws.receive_json()
        assert msg["event"] == "error"
        assert msg["code"] == "TENANT_CONCURRENCY_LIMIT_EXCEEDED"


def test_websocket_cancel_requested_in_flight_emits_cancelled_progress(monkeypatch: pytest.MonkeyPatch) -> None:
    app = build_test_app()
    client = TestClient(app)
    tenant_id = "ws-cancel-in-flight-tenant"
    session_id = _register_agent_and_session(client, tenant_id)
    run_id = "run_ws_cancel_in_flight"

    async def _fake_stream_turn(**kwargs):
        _ = kwargs
        yield {
            "event": "tool_progress",
            "call_id": "call_ws_in_flight_1",
            "tool_name": "echo_tool",
            "state": "running",
            "tool_status": "",
            "error_code": "",
            "correlation_id": run_id,
        }
        app.state.run_control_registry.request_cancel(
            tenant_id=tenant_id,
            run_id=run_id,
            reason="test_in_flight_cancel",
        )
        yield {"event": "output_delta", "delta": "ignored", "correlation_id": run_id}

    monkeypatch.setattr(turns_router_module, "_stream_turn", _fake_stream_turn)
    with client.websocket_connect(f"/tenants/{tenant_id}/sessions/{session_id}/ws", headers=_headers(tenant_id)) as ws:
        ws.send_json({"type": "turn", "input": "hello", "run_id": run_id})
        first = ws.receive_json()
        second = ws.receive_json()
        assert first["event"] == "tool_progress"
        assert second["event"] == "tool_progress"
        assert second["state"] == "cancelled"

    record = app.state.run_control_registry.get_run(tenant_id=tenant_id, run_id=run_id)
    assert record is not None
    assert record["status"] == "cancelled"
    assert record["terminal_event"] in {"cancel_requested_in_flight", "ws_task_cancelled"}


def test_websocket_turn_marks_error_terminal_when_stream_emits_error(monkeypatch: pytest.MonkeyPatch) -> None:
    app = build_test_app()
    client = TestClient(app)
    tenant_id = "ws-error-terminal-tenant"
    session_id = _register_agent_and_session(client, tenant_id)
    run_id = "run_ws_error_terminal_1"

    async def _fake_stream_turn(**kwargs):
        _ = kwargs
        yield {"event": "error", "code": "X", "message": "stream failed", "correlation_id": run_id}

    monkeypatch.setattr(turns_router_module, "_stream_turn", _fake_stream_turn)
    with client.websocket_connect(f"/tenants/{tenant_id}/sessions/{session_id}/ws", headers=_headers(tenant_id)) as ws:
        ws.send_json({"type": "turn", "input": "hello", "run_id": run_id})
        msg = ws.receive_json()
        assert msg["event"] == "error"
        assert msg["message"] == "stream failed"
    record = app.state.run_control_registry.get_run(tenant_id=tenant_id, run_id=run_id)
    assert record is not None
    assert record["status"] == "errored"
    assert record["terminal_message"] == "stream failed"


def test_websocket_disconnect_during_send_returns_early(monkeypatch: pytest.MonkeyPatch) -> None:
    app = build_test_app()
    client = TestClient(app)
    tenant_id = "ws-send-exception-tenant"
    session_id = _register_agent_and_session(client, tenant_id)
    run_id = "run_ws_send_exception_1"

    async def _fake_stream_turn(**kwargs):
        _ = kwargs
        await asyncio.sleep(0.1)
        yield {"event": "output_delta", "delta": "late", "correlation_id": run_id}

    monkeypatch.setattr(turns_router_module, "_stream_turn", _fake_stream_turn)
    with client.websocket_connect(f"/tenants/{tenant_id}/sessions/{session_id}/ws", headers=_headers(tenant_id)) as ws:
        ws.send_json({"type": "turn", "input": "hello", "run_id": run_id})
        # Force close before first event is emitted; send_json in task should fail gracefully.
    record = app.state.run_control_registry.get_run(tenant_id=tenant_id, run_id=run_id)
    assert record is not None


def test_websocket_send_json_exception_in_turn_task_is_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    app = build_test_app()
    client = TestClient(app)
    tenant_id = "ws-send-json-fail-tenant"
    session_id = _register_agent_and_session(client, tenant_id)
    run_id = "run_ws_send_json_fail_1"

    async def _fake_stream_turn(**kwargs):
        _ = kwargs
        yield {"event": "output_delta", "delta": "hello", "correlation_id": run_id}

    async def _raise_send_json(self, data, mode="text"):  # noqa: ARG001
        raise RuntimeError("socket closed during send")

    monkeypatch.setattr(turns_router_module, "_stream_turn", _fake_stream_turn)
    monkeypatch.setattr(turns_router_module.WebSocket, "send_json", _raise_send_json)

    with client.websocket_connect(f"/tenants/{tenant_id}/sessions/{session_id}/ws", headers=_headers(tenant_id)) as ws:
        ws.send_json({"type": "turn", "input": "hello", "run_id": run_id})
        # Let the server task run and hit the send_json exception path.
        time.sleep(0.2)
