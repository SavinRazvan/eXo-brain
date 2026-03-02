"""
File: test_slice1_transport.py
Path: tests/modules/api/test_slice1_transport.py
Role: Acceptance tests for Slice 1 — FastAPI transport layer, auth middleware, and tenant context.
Used By:
 - pytest
Depends On:
 - src/api/app.py
 - src/api/bootstrap.py
 - src/api/dependencies.py
 - src/api/middleware/auth.py
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from src.api.bootstrap import build_test_app
from src.api.middleware.auth import extract_identity, is_identity_usable
from src.identity.contracts import IdentityContext, TokenValidationState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _identity_header(subject: str = "user@test.com", roles: list | None = None, tenant_id: str = "tenant-1",
                     state: str = "valid") -> dict:
    payload = {
        "subject": subject,
        "roles": roles or ["user"],
        "tenant_id": tenant_id,
        "token_validation_state": state,
    }
    return {"X-Identity": json.dumps(payload)}


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def test_app_starts_and_health_endpoint_returns_ok() -> None:
    app = build_test_app()
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.json()["platform"] == "eXo-brain"


def test_app_state_has_required_objects() -> None:
    app = build_test_app()
    assert hasattr(app.state, "tenant_factory")
    assert hasattr(app.state, "provider_registry")
    assert hasattr(app.state, "policy_overlay_store")
    assert hasattr(app.state, "settings")


def test_openapi_schema_accessible() -> None:
    app = build_test_app()
    client = TestClient(app)
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    assert schema["info"]["title"] == "eXo-brain API"


# ---------------------------------------------------------------------------
# Auth middleware — extract_identity
# ---------------------------------------------------------------------------


def test_extract_identity_parses_valid_header() -> None:
    from fastapi import Request
    from unittest.mock import MagicMock

    mock_request = MagicMock(spec=Request)
    mock_request.headers = {"X-Identity": json.dumps({"subject": "alice", "tenant_id": "t1"})}
    identity = extract_identity(mock_request)
    assert identity is not None
    assert identity.subject == "alice"
    assert identity.tenant_id == "t1"


def test_extract_identity_returns_none_when_header_missing() -> None:
    from fastapi import Request
    from unittest.mock import MagicMock

    mock_request = MagicMock(spec=Request)
    mock_request.headers = {}
    identity = extract_identity(mock_request)
    assert identity is None


def test_extract_identity_returns_none_for_malformed_json() -> None:
    from fastapi import Request
    from unittest.mock import MagicMock

    mock_request = MagicMock(spec=Request)
    mock_request.headers = {"X-Identity": "not-json"}
    identity = extract_identity(mock_request)
    assert identity is None


def test_extract_identity_returns_none_when_subject_missing() -> None:
    from fastapi import Request
    from unittest.mock import MagicMock

    mock_request = MagicMock(spec=Request)
    mock_request.headers = {"X-Identity": json.dumps({"tenant_id": "t1"})}
    identity = extract_identity(mock_request)
    assert identity is None


# ---------------------------------------------------------------------------
# Auth middleware — is_identity_usable
# ---------------------------------------------------------------------------


def test_valid_token_state_is_usable() -> None:
    identity = IdentityContext(subject="u1", token_validation_state=TokenValidationState.VALID)
    assert is_identity_usable(identity) is True


def test_unknown_token_state_is_usable() -> None:
    identity = IdentityContext(subject="u1", token_validation_state=TokenValidationState.UNKNOWN)
    assert is_identity_usable(identity) is True


def test_rotation_required_token_state_is_usable() -> None:
    identity = IdentityContext(subject="u1", token_validation_state=TokenValidationState.ROTATION_REQUIRED)
    assert is_identity_usable(identity) is True


def test_invalid_token_state_is_rejected() -> None:
    identity = IdentityContext(subject="u1", token_validation_state=TokenValidationState.INVALID)
    assert is_identity_usable(identity) is False


def test_expired_token_state_is_rejected() -> None:
    identity = IdentityContext(subject="u1", token_validation_state=TokenValidationState.EXPIRED)
    assert is_identity_usable(identity) is False


# ---------------------------------------------------------------------------
# get_identity dependency — via a test endpoint
# ---------------------------------------------------------------------------


def _make_app_with_identity_endpoint():
    """Build a test app with an extra route that exercises get_identity and require_valid_identity."""
    from fastapi import Depends
    from src.api.dependencies import get_identity, require_valid_identity

    app = build_test_app()

    @app.get("/test/identity")
    async def identity_endpoint(identity: IdentityContext = Depends(get_identity)):
        return {"subject": identity.subject, "tenant_id": identity.tenant_id}

    @app.get("/test/require-valid")
    async def require_valid_endpoint(identity: IdentityContext = Depends(require_valid_identity)):
        return {"subject": identity.subject}

    return app


def test_get_identity_dependency_returns_401_when_header_missing() -> None:
    app = _make_app_with_identity_endpoint()
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/test/identity")
    assert resp.status_code == 401


def test_get_identity_dependency_parses_valid_header() -> None:
    app = _make_app_with_identity_endpoint()
    client = TestClient(app)
    resp = client.get("/test/identity", headers=_identity_header(subject="bob", tenant_id="t-bob"))
    assert resp.status_code == 200
    assert resp.json()["subject"] == "bob"
    assert resp.json()["tenant_id"] == "t-bob"


def test_require_valid_identity_rejects_invalid_token() -> None:
    app = _make_app_with_identity_endpoint()
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/test/require-valid", headers=_identity_header(state="invalid"))
    assert resp.status_code == 401


def test_require_valid_identity_rejects_expired_token() -> None:
    app = _make_app_with_identity_endpoint()
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/test/require-valid", headers=_identity_header(state="expired"))
    assert resp.status_code == 401


def test_require_valid_identity_allows_valid_token() -> None:
    app = _make_app_with_identity_endpoint()
    client = TestClient(app)
    resp = client.get("/test/require-valid", headers=_identity_header(state="valid"))
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# get_tenant_context dependency — tenant isolation
# ---------------------------------------------------------------------------


def _make_app_with_tenant_endpoint():
    from fastapi import Depends
    from src.api.dependencies import get_tenant_context
    from src.runtime.tenant_runtime import TenantRuntimeContext

    app = build_test_app()

    @app.get("/test/tenants/{tenant_id}/tool-count")
    async def tool_count(ctx: TenantRuntimeContext = Depends(get_tenant_context)):
        return {"tenant_id": ctx.tenant_id, "tool_count": len(ctx.tool_registry.list_tools())}

    return app


def test_get_tenant_context_returns_isolated_context_per_tenant() -> None:
    app = _make_app_with_tenant_endpoint()
    client = TestClient(app)

    resp_a = client.get("/test/tenants/tenant-alpha/tool-count",
                        headers=_identity_header(tenant_id="tenant-alpha"))
    resp_b = client.get("/test/tenants/tenant-beta/tool-count",
                        headers=_identity_header(tenant_id="tenant-beta"))

    assert resp_a.status_code == 200
    assert resp_b.status_code == 200
    assert resp_a.json()["tenant_id"] == "tenant-alpha"
    assert resp_b.json()["tenant_id"] == "tenant-beta"


def test_get_tenant_context_same_tenant_returns_same_context() -> None:
    """Two requests for the same tenant_id must hit the same cached context."""
    app = _make_app_with_tenant_endpoint()

    from fastapi import Depends
    from src.api.dependencies import get_tenant_context
    from src.runtime.tenant_runtime import TenantRuntimeContext

    seen_ids: list[int] = []

    @app.get("/test/tenants/{tenant_id}/ctx-id")
    async def ctx_id(ctx: TenantRuntimeContext = Depends(get_tenant_context)):
        seen_ids.append(id(ctx))
        return {"ctx_id": id(ctx)}

    client = TestClient(app)
    r1 = client.get("/test/tenants/same-tenant/ctx-id",
                    headers=_identity_header(tenant_id="same-tenant"))
    r2 = client.get("/test/tenants/same-tenant/ctx-id",
                    headers=_identity_header(tenant_id="same-tenant"))
    assert r1.json()["ctx_id"] == r2.json()["ctx_id"]


def test_tools_registered_in_one_tenant_not_visible_in_another() -> None:
    """Tenant isolation: registering a tool in A must not appear in B."""
    app = _make_app_with_tenant_endpoint()
    client = TestClient(app)
    factory = app.state.tenant_factory

    from src.tools.registry import ToolDescriptor
    ctx_a = factory.get_or_create("isolated-a")
    ctx_a.tool_registry.register(ToolDescriptor(name="secret_tool", handler=lambda: None))

    resp_a = client.get("/test/tenants/isolated-a/tool-count",
                        headers=_identity_header(tenant_id="isolated-a"))
    resp_b = client.get("/test/tenants/isolated-b/tool-count",
                        headers=_identity_header(tenant_id="isolated-b"))

    assert resp_a.json()["tool_count"] == 1
    assert resp_b.json()["tool_count"] == 0
