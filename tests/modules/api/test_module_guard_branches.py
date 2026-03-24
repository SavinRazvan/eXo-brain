"""
File: test_module_guard_branches.py
Path: tests/modules/api/test_module_guard_branches.py
Role: Cover module-guard fallback branches added during the modular monolith refactor.
Used By:
 - pytest
Depends On:
 - src/api/dependencies.py
 - src/api/routers/admin_keys.py
 - src/api/routers/audit.py
 - src/api/routers/providers.py
 - src/api/routers/runtime_control.py
 - src/api/routers/sessions.py
 - src/api/routers/tenants.py
 - src/api/routers/tools.py
 - src/api/routers/turns.py
Notes:
 - These tests exercise direct helper and error branches without going through full HTTP flows.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.api import dependencies
from src.api.routers import admin_keys
from src.api.routers import audit as audit_router
from src.api.routers import providers, runtime_control, sessions, tenants
from src.api.routers import tools as tools_router
from src.api.routers import turns
from src.api.schemas.auth_schemas import ApiKeyCreateRequest
from src.api.schemas.provider_schemas import ProviderRegisterRequest
from src.api.schemas.session_schemas import SessionCreateRequest
from src.api.schemas.turn_schemas import TurnSubmitRequest
from src.identity.contracts import IdentityContext, TokenValidationState
from src.modules.session_runtime.service import SessionRuntimeError
from src.policies.entitlements import EntitledFeature


def _identity(*, tenant_id: str = "t1", roles: list[str] | None = None) -> IdentityContext:
    return IdentityContext(
        subject="user@example.com",
        tenant_id=tenant_id,
        roles=roles or ["platform_admin", "entitlement_pro"],
        token_validation_state=TokenValidationState.VALID,
    )


def _request(path: str = "/tenants/t1/admin/runtime", method: str = "GET", **state_attrs):
    return SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(**state_attrs)),
        url=SimpleNamespace(path=path),
        scope={"route": SimpleNamespace(path=path)},
        method=method,
        headers={},
    )


class _FakeWebSocket:
    def __init__(self, path: str) -> None:
        self.url = SimpleNamespace(path=path)
        self.app = SimpleNamespace(state=SimpleNamespace())
        self.closed: list[tuple[int, str]] = []

    async def close(self, code: int, reason: str) -> None:
        self.closed.append((code, reason))


def test_dependencies_fall_back_to_raw_app_state_when_modules_are_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dependencies, "get_app_modules", lambda request: None)
    request = _request(
        tenant_factory="factory",
        policy_overlay_store="overlay-store",
        tool_store="tool-store",
        agent_store="agent-store",
        tool_version_store="tool-version-store",
        settings=SimpleNamespace(
            auth=SimpleNamespace(
                allow_cross_tenant_admin=True,
                cross_tenant_admin_roles=["super_admin"],
            )
        ),
    )

    assert dependencies._get_tenant_factory(request) == "factory"
    assert dependencies._get_policy_overlay_store(request) == "overlay-store"
    assert dependencies.get_tool_store(request) == "tool-store"
    assert dependencies.get_agent_store(request) == "agent-store"
    assert dependencies.get_tool_version_store(request) == "tool-version-store"
    assert dependencies._cross_tenant_admin_allowed(
        request,
        _identity(tenant_id="other", roles=["super_admin"]),
    )

    blank_roles_request = _request(
        settings=SimpleNamespace(
            auth=SimpleNamespace(
                allow_cross_tenant_admin=True,
                cross_tenant_admin_roles=["", "   "],
            )
        ),
    )
    assert not dependencies._cross_tenant_admin_allowed(
        blank_roles_request,
        _identity(tenant_id="other", roles=["super_admin"]),
    )

    disabled_request = _request(
        settings=SimpleNamespace(
            auth=SimpleNamespace(
                allow_cross_tenant_admin=False,
                cross_tenant_admin_roles=["super_admin"],
            )
        ),
    )
    assert not dependencies._cross_tenant_admin_allowed(
        disabled_request,
        _identity(tenant_id="other", roles=["super_admin"]),
    )


@pytest.mark.asyncio
async def test_admin_key_routes_raise_503_when_identity_access_module_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request()
    identity = _identity()
    body = ApiKeyCreateRequest(tenant_id="t1", subject="svc@example.com", roles=["reader"], description="")
    monkeypatch.setattr(admin_keys, "get_app_modules", lambda request: None)

    with pytest.raises(HTTPException, match="Identity access module is not configured"):
        await admin_keys.create_api_key(body=body, request=request, identity=identity)
    with pytest.raises(HTTPException, match="Identity access module is not configured"):
        await admin_keys.list_api_keys(request=request, tenant_id=None, identity=identity)
    with pytest.raises(HTTPException, match="Identity access module is not configured"):
        await admin_keys.delete_api_key(key_id="key-1", request=request, identity=identity)


def test_audit_and_tenant_helpers_cover_missing_module_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    request = _request()
    monkeypatch.setattr(audit_router, "get_app_modules", lambda request: None)
    monkeypatch.setattr(tenants, "get_app_modules", lambda request: None)

    with pytest.raises(HTTPException, match="Audit observability module is not configured"):
        audit_router._audit_module(request)
    assert tenants._audit_pipeline(request) is None
    assert tenants._run_registry(request) is None


def test_provider_helpers_raise_503_when_modules_are_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    request = _request()
    monkeypatch.setattr(providers, "get_app_modules", lambda request: None)

    with pytest.raises(HTTPException, match="Provider management module is not configured"):
        providers._get_provider_registry(request)
    assert providers._get_provider_service(request) is None
    with pytest.raises(HTTPException, match="Provider management module is not configured"):
        providers._get_provider_store(request)
    with pytest.raises(HTTPException, match="Session runtime module is not configured"):
        providers._get_session_store(request)
    with pytest.raises(HTTPException, match="Application modules are not configured"):
        providers._can_use_provider_drain(request, _identity())


def test_provider_store_helper_returns_store_when_modules_exist(monkeypatch: pytest.MonkeyPatch) -> None:
    request = _request()
    fake_modules = SimpleNamespace(provider_management=SimpleNamespace(store="provider-store"))
    monkeypatch.setattr(providers, "get_app_modules", lambda request: fake_modules)

    assert providers._get_provider_store(request) == "provider-store"


@pytest.mark.asyncio
async def test_provider_routes_raise_503_when_provider_service_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    request = _request()
    identity = _identity()
    body = ProviderRegisterRequest(
        provider_id="provider-a",
        display_name="Provider A",
        adapter_class_ref="src.runtime.openai_agents_runtime.OpenAIAgentsRuntimeAdapter",
    )
    monkeypatch.setattr(providers, "get_app_modules", lambda request: None)

    with pytest.raises(HTTPException, match="Provider management module is not configured"):
        await providers.register_provider(body=body, request=request, identity=identity)
    with pytest.raises(HTTPException, match="Provider management module is not configured"):
        await providers.unregister_provider(
            provider_id="provider-a",
            request=request,
            force_drain=False,
            identity=identity,
        )


@pytest.mark.asyncio
async def test_session_routes_cover_missing_module_and_service_error_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request()
    body = SessionCreateRequest(agent_id="agent-a", provider_id="openai-test")
    identity = _identity()

    monkeypatch.setattr(sessions, "get_app_modules", lambda request: None)
    with pytest.raises(HTTPException, match="Session runtime module is not configured"):
        await sessions.create_session(tenant_id="t1", body=body, request=request, identity=identity)
    with pytest.raises(HTTPException, match="Session runtime module is not configured"):
        await sessions.get_session(tenant_id="t1", session_id="sess-1", request=request, _identity=identity)

    class _ErrorService:
        async def create_session(self, **_: object):
            raise SessionRuntimeError(status_code=422, detail="create boom")

        async def get_session(self, **_: object):
            raise SessionRuntimeError(status_code=410, detail="get boom")

    fake_modules = SimpleNamespace(session_runtime=SimpleNamespace(service=_ErrorService()))
    monkeypatch.setattr(sessions, "get_app_modules", lambda request: fake_modules)
    with pytest.raises(HTTPException, match="create boom"):
        await sessions.create_session(tenant_id="t1", body=body, request=request, identity=identity)
    with pytest.raises(HTTPException, match="get boom"):
        await sessions.get_session(tenant_id="t1", session_id="sess-1", request=request, _identity=identity)


@pytest.mark.asyncio
async def test_runtime_control_module_guards_cover_unconfigured_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request("/tenants/t1/admin/byoc/governance-metrics")
    identity = _identity()
    monkeypatch.setattr(runtime_control, "get_app_modules", lambda request: None)

    with pytest.raises(HTTPException, match="Application modules are not configured"):
        await runtime_control._enforce_feature_entitlement(
            request=request,
            tenant_id="t1",
            identity=identity,
            feature=EntitledFeature.GOVERNANCE_RUNTIME_ADMIN_CONTROLS,
            surface="runtime_control_admin",
        )

    assert runtime_control._resolve_ingress_budget_recorder(request) is None

    adapter = SimpleNamespace(
        backend_id="byoc_pull_worker_runtime",
        control_stats=lambda: {},
    )
    ctx = SimpleNamespace(tool_executor=SimpleNamespace(execution_adapter=lambda: adapter))
    with pytest.raises(HTTPException, match="Application modules are not configured"):
        await runtime_control.get_byoc_governance_metrics(
            tenant_id="t1",
            request=request,
            ctx=ctx,
            _identity=identity,
        )


def test_tool_helper_functions_raise_503_without_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    request = _request()
    monkeypatch.setattr(tools_router, "get_app_modules", lambda request: None)

    for helper in (
        tools_router._artifact_signing_secret,
        tools_router._limits,
        tools_router._tool_upload_rate_limiter,
        tools_router._tool_audit_pipeline,
        tools_router._tool_artifact_store,
    ):
        with pytest.raises(HTTPException, match="Application modules are not configured"):
            helper(request)


@pytest.mark.asyncio
async def test_turn_routes_cover_missing_module_http_and_websocket_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request("/tenants/t1/sessions/sess-1/turns", method="POST")
    monkeypatch.setattr(turns, "get_app_modules", lambda request: None)

    with pytest.raises(HTTPException, match="Session runtime module is not configured"):
        turns._get_factory(request)
    with pytest.raises(HTTPException, match="Session runtime module is not configured"):
        turns._get_run_registry(request)

    monkeypatch.setattr(turns, "app_modules_from_requestlike", lambda requestlike: None)
    websocket = _FakeWebSocket("/tenants/t1/admin/sessions/sess-1/ws")
    assert not turns._websocket_cross_tenant_admin_allowed(
        websocket,
        _identity(tenant_id="other", roles=["super_admin"]),
    )

    await turns.websocket_turn(tenant_id="t1", session_id="sess-1", websocket=websocket)
    assert websocket.closed == [(1011, "Application modules are not configured.")]

    monkeypatch.setattr(turns, "_get_factory", lambda request: SimpleNamespace(get_session_runtime=lambda session_id: object()))
    monkeypatch.setattr(turns, "_get_run_registry", lambda request: object())
    monkeypatch.setattr(turns, "get_app_modules", lambda request: None)
    ctx = SimpleNamespace(tool_executor=SimpleNamespace(execution_adapter=lambda: None))
    with pytest.raises(HTTPException, match="Application modules are not configured"):
        await turns.submit_turn_sse(
            tenant_id="t1",
            session_id="sess-1",
            body=TurnSubmitRequest(input="hello"),
            request=request,
            ctx=ctx,
            identity=_identity(),
        )
