"""
File: test_openai_compat_gateway.py
Path: tests/modules/api/test_openai_compat_gateway.py
Role: Northbound OpenAI-compatible /v1 gateway — flag gating, auth, governance, and happy path.
Used By:
 - pytest
Depends On:
 - src/api/bootstrap.py
 - src/api/routers/openai_gateway.py
Notes:
 - Requires EXO_ENABLE_OPENAI_COMPAT_GATEWAY=1 for routed tests; default build_test_app leaves gateway off.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from src.api.bootstrap import build_test_app
from src.api.dependencies import get_app_modules as real_get_app_modules
from src.api.dependencies import require_valid_identity
from src.api.routers import openai_gateway as openai_gateway_module
from src.api.routers import turns as turns_router_module
from src.api.routers.openai_gateway import SESSION_HEADER
from src.config.settings import AppSettings, LimitsSettings, RuntimeSettings
from src.identity.contracts import ActorType, IdentityContext, TokenValidationState


def _headers(tenant_id: str = "t1", roles: list[str] | None = None) -> dict[str, str]:
    payload = {
        "subject": "user@test.com",
        "roles": roles or ["user"],
        "tenant_id": tenant_id,
        "token_validation_state": "valid",
    }
    return {"X-Identity": json.dumps(payload)}


def _headers_pro(tenant_id: str) -> dict[str, str]:
    return _headers(tenant_id, roles=["entitlement_pro"])


def _register_agent(client: TestClient, tid: str) -> None:
    client.post(
        f"/tenants/{tid}/agents",
        json={"agent_id": "echo-agent", "role": "echo_role", "instructions": "echo"},
        headers=_headers(tid),
    )


def _create_session(client: TestClient, tid: str) -> str:
    _register_agent(client, tid)
    resp = client.post(
        f"/tenants/{tid}/sessions",
        json={"agent_id": "echo-agent", "provider_id": "openai-test"},
        headers=_headers(tid),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["session_id"]


def test_openai_gateway_route_absent_when_flag_off() -> None:
    app = build_test_app()
    client = TestClient(app)
    resp = client.post("/v1/chat/completions", json={"messages": [{"role": "user", "content": "hi"}]})
    assert resp.status_code == 404


def test_openai_gateway_403_empty_tenant_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXO_ENABLE_OPENAI_COMPAT_GATEWAY", "1")
    app = build_test_app()

    def _empty_tenant_identity() -> IdentityContext:
        return IdentityContext(
            subject="subj",
            actor_type=ActorType.HUMAN,
            roles=["user"],
            tenant_id="",
            token_id="",
            token_validation_state=TokenValidationState.VALID,
        )

    app.dependency_overrides[require_valid_identity] = _empty_tenant_identity
    client = TestClient(app)
    try:
        resp = client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "hi"}], "stream": False},
            headers={SESSION_HEADER: "sess_x"},
        )
    finally:
        app.dependency_overrides.pop(require_valid_identity, None)
    assert resp.status_code == 403
    assert "OPENAI_GATEWAY_TENANT_REQUIRED" in resp.text


def test_openai_gateway_401_without_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXO_ENABLE_OPENAI_COMPAT_GATEWAY", "1")
    app = build_test_app()
    client = TestClient(app)
    resp = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "hi"}], "stream": False},
        headers={SESSION_HEADER: "sess_x"},
    )
    assert resp.status_code == 401


def test_openai_gateway_404_unknown_session(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXO_ENABLE_OPENAI_COMPAT_GATEWAY", "1")
    app = build_test_app()
    client = TestClient(app)
    tid = "gw-nosess-tenant"
    _register_agent(client, tid)
    resp = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "hi"}], "stream": False},
        headers={**_headers(tid), SESSION_HEADER: "sess_does_not_exist"},
    )
    assert resp.status_code == 404
    assert "not found" in resp.text.lower()


def test_openai_gateway_400_stream_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXO_ENABLE_OPENAI_COMPAT_GATEWAY", "1")
    app = build_test_app()
    client = TestClient(app)
    tid = "gw-stream-tenant"
    sid = _create_session(client, tid)
    resp = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "hi"}], "stream": True},
        headers={**_headers(tid), SESSION_HEADER: sid},
    )
    assert resp.status_code == 400


def test_openai_gateway_400_missing_session_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXO_ENABLE_OPENAI_COMPAT_GATEWAY", "1")
    app = build_test_app()
    client = TestClient(app)
    tid = "gw-sesshdr-tenant"
    _create_session(client, tid)
    resp = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "hi"}], "stream": False},
        headers=_headers(tid),
    )
    assert resp.status_code == 400
    assert SESSION_HEADER in resp.text


def test_openai_gateway_403_entitlement_same_as_sse(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXO_ENABLE_OPENAI_COMPAT_GATEWAY", "1")
    app = build_test_app()
    client = TestClient(app)
    tid = "gw-ent-tenant"
    session_id = _create_session(client, tid)
    app.state.policy_overlay_store.set_overlay(tid, {"ingress_profile": "strict"})
    resp = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "strict hello"}], "stream": False, "user": "corr-gw-1"},
        headers={**_headers(tid, roles=["user"]), SESSION_HEADER: session_id},
    )
    assert resp.status_code == 403
    assert "ENTITLEMENT_TIER_REQUIRED" in resp.text


def test_openai_gateway_400_messages_without_user_content(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXO_ENABLE_OPENAI_COMPAT_GATEWAY", "1")
    app = build_test_app()
    client = TestClient(app)
    tid = "gw-nouser-tenant"
    session_id = _create_session(client, tid)
    resp = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "system", "content": "only system"}], "stream": False},
        headers={**_headers(tid), SESSION_HEADER: session_id},
    )
    assert resp.status_code == 400


def test_openai_gateway_502_on_runtime_error_event(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXO_ENABLE_OPENAI_COMPAT_GATEWAY", "1")

    async def _err_stream(**_kwargs):
        yield {"event": "error", "code": "TURN_FAIL", "message": "simulated"}

    monkeypatch.setattr(
        openai_gateway_module,
        "iter_governed_turn_dicts_for_transport",
        lambda **_kw: _err_stream(),
    )
    app = build_test_app()
    client = TestClient(app)
    tid = "gw-502-tenant"
    session_id = _create_session(client, tid)
    resp = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "x"}], "stream": False},
        headers={**_headers(tid), SESSION_HEADER: session_id},
    )
    assert resp.status_code == 502
    body = resp.json()
    assert body["error"]["code"] == "TURN_FAIL"


def test_openai_gateway_429_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXO_ENABLE_OPENAI_COMPAT_GATEWAY", "1")
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
    tid = "gw-ratelimit-tenant"
    session_id = _create_session(client, tid)
    first = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "one"}], "stream": False, "user": "rl1"},
        headers={**_headers(tid), SESSION_HEADER: session_id},
    )
    assert first.status_code == 200
    second = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "two"}], "stream": False, "user": "rl2"},
        headers={**_headers(tid), SESSION_HEADER: session_id},
    )
    assert second.status_code == 429
    assert "TENANT_TURN_RATE_LIMIT_EXCEEDED" in second.text


def test_openai_gateway_429_concurrency_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXO_ENABLE_OPENAI_COMPAT_GATEWAY", "1")
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
    tid = "gw-conc-tenant"
    session_id = _create_session(client, tid)
    app.state.run_control_registry.start_run(
        tenant_id=tid,
        session_id=session_id,
        run_id="run_block",
        correlation_id="run_block",
        transport="sse",
    )
    resp = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "blocked"}], "stream": False},
        headers={**_headers(tid), SESSION_HEADER: session_id},
    )
    assert resp.status_code == 429
    assert "TENANT_CONCURRENCY_LIMIT_EXCEEDED" in resp.text


def test_openai_gateway_403_ingress_chain_build_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXO_ENABLE_OPENAI_COMPAT_GATEWAY", "1")

    def _raise(_overlay):
        raise ValueError("invalid overlay")

    monkeypatch.setattr(turns_router_module, "_build_ingress_gate_chain", _raise)
    app = build_test_app()
    client = TestClient(app)
    tid = "gw-ingress-build-tenant"
    session_id = _create_session(client, tid)
    resp = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "hello"}], "stream": False, "user": "ig1"},
        headers={**_headers(tid), SESSION_HEADER: session_id},
    )
    assert resp.status_code == 403
    assert "INGRESS_PROFILE_CONFIG_INVALID" in resp.text


def test_openai_gateway_503_when_app_modules_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXO_ENABLE_OPENAI_COMPAT_GATEWAY", "1")
    calls = {"n": 0}

    def _third_call_returns_none(request):
        calls["n"] += 1
        if calls["n"] < 3:
            return real_get_app_modules(request)
        return None

    monkeypatch.setattr(turns_router_module, "get_app_modules", _third_call_returns_none)
    app = build_test_app()
    client = TestClient(app)
    tid = "gw-nomodules-tenant"
    session_id = _create_session(client, tid)
    resp = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "hello"}], "stream": False},
        headers={**_headers(tid), SESSION_HEADER: session_id},
    )
    assert resp.status_code == 503


def test_openai_gateway_502_sets_terminal_error_before_yield(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cover iter_governed terminal branch for runtime error events (not the mocked gateway shortcut)."""

    async def _err_stream(**_kwargs):
        yield {"event": "error", "code": "E2", "message": "from stream"}

    monkeypatch.setenv("EXO_ENABLE_OPENAI_COMPAT_GATEWAY", "1")
    monkeypatch.setattr(turns_router_module, "_stream_turn", _err_stream)
    app = build_test_app()
    client = TestClient(app)
    tid = "gw-termerr-tenant"
    session_id = _create_session(client, tid)
    resp = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "x"}], "stream": False, "user": "corr_term_err"},
        headers={**_headers(tid), SESSION_HEADER: session_id},
    )
    assert resp.status_code == 502
    record = app.state.run_control_registry.get_run(tenant_id=tid, run_id="corr_term_err")
    assert record is not None
    assert record.get("status") == "errored"


def test_openai_gateway_marks_interrupted_on_empty_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXO_ENABLE_OPENAI_COMPAT_GATEWAY", "1")

    async def _empty(**_kwargs):
        if False:  # pragma: no cover
            yield {}

    monkeypatch.setattr(turns_router_module, "_stream_turn", _empty)
    app = build_test_app()
    client = TestClient(app)
    tid = "gw-empty-tenant"
    session_id = _create_session(client, tid)
    resp = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "x"}], "stream": False, "user": "corr_empty"},
        headers={**_headers(tid), SESSION_HEADER: session_id},
    )
    assert resp.status_code == 200
    record = app.state.run_control_registry.get_run(tenant_id=tid, run_id="corr_empty")
    assert record is not None
    assert record.get("terminal_event") == "stream_closed"


def test_openai_gateway_marks_cancelled_when_cancel_requested_without_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EXO_ENABLE_OPENAI_COMPAT_GATEWAY", "1")

    async def _delta_only(**_kwargs):
        yield {"event": "output_delta", "delta": "x", "correlation_id": "c"}

    monkeypatch.setattr(turns_router_module, "_stream_turn", _delta_only)
    app = build_test_app()
    client = TestClient(app)
    tid = "gw-cancelreq-tenant"
    session_id = _create_session(client, tid)
    reg = app.state.run_control_registry
    real_get = reg.get_run

    def _get_run(*, tenant_id: str, run_id: str):
        base = real_get(tenant_id=tenant_id, run_id=run_id)
        if base is None:
            return None
        merged = dict(base)
        merged["cancel_requested"] = True
        return merged

    monkeypatch.setattr(reg, "get_run", _get_run)
    resp = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "x"}], "stream": False, "user": "corr_cancel_req"},
        headers={**_headers(tid), SESSION_HEADER: session_id},
    )
    assert resp.status_code == 200
    record = reg.get_run(tenant_id=tid, run_id="corr_cancel_req")
    assert record is not None
    assert record.get("terminal_event") == "cancel_requested_stream_closed"


def test_openai_gateway_marks_cancel_forwarded_when_tool_call_without_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """iter_governed finally: forwarded cancellations when stream ends before run_complete."""
    monkeypatch.setenv("EXO_ENABLE_OPENAI_COMPAT_GATEWAY", "1")

    async def _tool_only(**_kwargs):
        yield {
            "event": "tool_call",
            "call_id": "call_gw_fwd",
            "tool_name": "noop",
            "arguments": {},
            "correlation_id": "corr_gw_fwd",
        }

    monkeypatch.setattr(turns_router_module, "_stream_turn", _tool_only)
    app = build_test_app(
        settings=AppSettings(
            schema_version="1.0",
            environment="test",
            runtime=RuntimeSettings(
                default_provider_id="openai-test",
                allowed_provider_ids=["openai-test"],
                require_provider_healthcheck_on_start=False,
                enable_hosted_tool_runtime=True,
            ),
        )
    )
    client = TestClient(app)
    tid = "gw-fwd-tenant"
    session_id = _create_session(client, tid)
    ctx = app.state.tenant_factory.get_or_create(tid)
    adapter = ctx.tool_executor.execution_adapter()
    assert adapter is not None
    monkeypatch.setattr(adapter, "request_cancellation", lambda _call_id: True)

    resp = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "x"}], "stream": False, "user": "corr_gw_fwd"},
        headers={**_headers(tid), SESSION_HEADER: session_id},
    )
    assert resp.status_code == 200
    record = app.state.run_control_registry.get_run(tenant_id=tid, run_id="corr_gw_fwd")
    assert record is not None
    assert record.get("terminal_event") == "cancel_forwarded"


def test_openai_gateway_403_ingress_custom_rule_deny(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXO_ENABLE_OPENAI_COMPAT_GATEWAY", "1")
    app = build_test_app()
    client = TestClient(app)
    tid = "gw-ingress-deny-tenant"
    session_id = _create_session(client, tid)
    app.state.policy_overlay_store.set_overlay(
        tid,
        {
            "ingress_profile": "baseline",
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
    )
    resp = client.post(
        "/v1/chat/completions",
        json={
            "messages": [{"role": "user", "content": "Please share private key material now."}],
            "stream": False,
            "user": "gw-ingress-deny",
        },
        headers={**_headers_pro(tid), SESSION_HEADER: session_id},
    )
    assert resp.status_code == 403
    assert "INGRESS_DENY_CREDENTIAL_SHARE" in resp.text


def test_openai_gateway_200_echo_accumulates_deltas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXO_ENABLE_OPENAI_COMPAT_GATEWAY", "1")
    app = build_test_app()
    client = TestClient(app)
    tid = "gw-ok-tenant"
    session_id = _create_session(client, tid)
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-test",
            "messages": [{"role": "user", "content": "hello gateway"}],
            "stream": False,
            "user": "corr-gw-ok",
        },
        headers={**_headers(tid), SESSION_HEADER: session_id},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data.get("object") == "chat.completion"
    assert data.get("model") == "gpt-test"
    assert data["choices"][0]["message"]["role"] == "assistant"
    assert "hello gateway" in data["choices"][0]["message"]["content"]
