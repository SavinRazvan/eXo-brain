"""
File: test_auth_jwt.py
Path: tests/modules/api/test_auth_jwt.py
Role: Acceptance tests for Slice 1 Step B — JWT Bearer authentication.
Used By:
 - pytest
Depends On:
 - src/identity/jwt_resolver.py
 - src/api/middleware/auth.py
Notes:
 - Tests cover decode_jwt directly and end-to-end via TestClient.
 - Uses HS256 with a fixed test secret; PyJWT is a required dependency.
"""

from __future__ import annotations

import json
import time

import jwt
import pytest

from src.identity.contracts import IdentityContext, TokenValidationState
from src.identity.jwt_resolver import decode_jwt


# ≥32 bytes for HS256 per PyJWT recommendation (avoids InsecureKeyLengthWarning noise).
_SECRET = "0123456789abcdef0123456789abcdef0123456789ab"
_ALG = "HS256"


# ---------------------------------------------------------------------------
# Unit tests — decode_jwt
# ---------------------------------------------------------------------------


def _make_token(
    sub: str = "alice",
    tenant_id: str = "t1",
    roles: list[str] | None = None,
    exp_offset: int = 3600,
    extra: dict | None = None,
) -> str:
    payload: dict = {
        "sub": sub,
        "tenant_id": tenant_id,
        "roles": ["user"] if roles is None else roles,
        "exp": int(time.time()) + exp_offset,
        "iat": int(time.time()),
        "jti": "test-jti-001",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, _SECRET, algorithm=_ALG)


def test_decode_jwt_valid_token() -> None:
    token = _make_token(sub="alice", tenant_id="t1", roles=["admin", "user"])
    identity = decode_jwt(token, secret=_SECRET, algorithm=_ALG)
    assert identity is not None
    assert identity.subject == "alice"
    assert identity.tenant_id == "t1"
    assert identity.roles == ["admin", "user"]
    assert identity.token_validation_state == TokenValidationState.VALID


def test_decode_jwt_expired_token() -> None:
    token = _make_token(exp_offset=-100)
    identity = decode_jwt(token, secret=_SECRET, algorithm=_ALG)
    assert identity is not None
    assert identity.token_validation_state == TokenValidationState.EXPIRED


def test_decode_jwt_wrong_secret_returns_none() -> None:
    token = _make_token()
    identity = decode_jwt(token, secret="fedcba9876543210fedcba9876543210", algorithm=_ALG)
    assert identity is None


def test_decode_jwt_invalid_token_string_returns_none() -> None:
    identity = decode_jwt("this.is.not.a.real.jwt", secret=_SECRET, algorithm=_ALG)
    assert identity is None


def test_decode_jwt_no_sub_claim_returns_none() -> None:
    payload = {
        "tenant_id": "t1",
        "roles": ["user"],
        "exp": int(time.time()) + 3600,
    }
    token = jwt.encode(payload, _SECRET, algorithm=_ALG)
    identity = decode_jwt(token, secret=_SECRET, algorithm=_ALG)
    assert identity is None


def test_decode_jwt_blank_sub_returns_none() -> None:
    payload = {
        "sub": "   ",
        "exp": int(time.time()) + 3600,
    }
    token = jwt.encode(payload, _SECRET, algorithm=_ALG)
    identity = decode_jwt(token, secret=_SECRET, algorithm=_ALG)
    assert identity is None


def test_decode_jwt_no_secret_configured_returns_none() -> None:
    token = _make_token()
    identity = decode_jwt(token, secret="", algorithm=_ALG)
    assert identity is None


def test_decode_jwt_default_tenant_id() -> None:
    """Token without tenant_id claim defaults to 'default'."""
    payload = {
        "sub": "bob",
        "exp": int(time.time()) + 3600,
    }
    token = jwt.encode(payload, _SECRET, algorithm=_ALG)
    identity = decode_jwt(token, secret=_SECRET, algorithm=_ALG)
    assert identity is not None
    assert identity.tenant_id == "default"


def test_decode_jwt_empty_roles() -> None:
    token = _make_token(roles=[])
    identity = decode_jwt(token, secret=_SECRET, algorithm=_ALG)
    assert identity is not None
    assert identity.roles == []


# ---------------------------------------------------------------------------
# Integration tests — JWT via TestClient
# ---------------------------------------------------------------------------


def _build_jwt_app(secret: str, algorithm: str = "HS256"):
    """Build a test app with JWT configured in AuthSettings."""
    from src.api.app import create_app
    from src.api.bootstrap import bootstrap
    from src.config.provider_registry import (
        AuthConfig, EndpointApiType, EndpointConfig, ModelDefaults,
        ProviderProfile, ProviderRecord, ProviderRegistry,
    )
    from src.config.settings import AppSettings, AuthSettings, RuntimeSettings
    from src.runtime.openai_agents_runtime import OpenAIAgentsRuntimeAdapter

    auth_settings = AuthSettings(jwt_secret=secret, algorithm=algorithm)
    settings = AppSettings(
        schema_version="1.0",
        environment="test",
        runtime=RuntimeSettings(
            default_provider_id="openai-test",
            allowed_provider_ids=["openai-test"],
            require_provider_healthcheck_on_start=False,
        ),
        auth=auth_settings,
    )
    adapter = OpenAIAgentsRuntimeAdapter(provider_id="openai-test")
    record = ProviderRecord(
        provider_id="openai-test",
        display_name="Test OpenAI",
        adapter_class="OpenAIAgentsRuntimeAdapter",
        enabled=True,
        profile=ProviderProfile.MANAGED_VENDOR,
        priority=1,
        endpoint=EndpointConfig(
            base_url="https://api.openai.com",
            api_type=EndpointApiType.OPENAI_NATIVE,
        ),
        auth=AuthConfig(type="api_key", api_key_env_var=""),
        model_defaults=ModelDefaults(model="gpt-4o-mini"),
    )
    provider_registry = ProviderRegistry(
        settings=settings,
        providers=[record],
        adapters={"openai-test": adapter},
    )
    app = create_app()
    bootstrap(app, provider_registry, settings, persistence_backend="memory")
    return app


def test_bearer_jwt_returns_200() -> None:
    """A valid JWT in Authorization: Bearer is accepted by the API."""
    from fastapi.testclient import TestClient

    app = _build_jwt_app(_SECRET)
    token = _make_token(sub="alice", tenant_id="t1")
    with TestClient(app) as client:
        resp = client.get("/health", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


def test_bearer_expired_jwt_returns_401() -> None:
    """An expired JWT returns 401."""
    from fastapi.testclient import TestClient

    app = _build_jwt_app(_SECRET)
    token = _make_token(exp_offset=-100)
    with TestClient(app) as client:
        resp = client.get(
            "/tenants/t1/tools",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 401


def test_bearer_invalid_jwt_returns_401() -> None:
    """A garbage Bearer token returns 401."""
    from fastapi.testclient import TestClient

    app = _build_jwt_app(_SECRET)
    with TestClient(app) as client:
        resp = client.get(
            "/tenants/t1/tools",
            headers={"Authorization": "Bearer not.a.real.jwt"},
        )
    assert resp.status_code == 401


def test_bearer_jwt_wrong_secret_returns_401() -> None:
    """A JWT signed with a different secret returns 401."""
    from fastapi.testclient import TestClient

    app = _build_jwt_app(_SECRET)
    bad_token = _make_token(sub="eve")
    # Re-encode with a different secret
    bad_token = jwt.encode(
        {"sub": "eve", "exp": int(time.time()) + 3600},
        "fedcba9876543210fedcba9876543210",
        algorithm=_ALG,
    )
    with TestClient(app) as client:
        resp = client.get(
            "/tenants/t1/tools",
            headers={"Authorization": f"Bearer {bad_token}"},
        )
    assert resp.status_code == 401


def test_extract_identity_returns_none_when_bearer_token_empty() -> None:
    """Bearer header present but blank token hits auth middleware early return."""
    import asyncio
    from unittest.mock import MagicMock

    from src.api.app import create_app
    from src.api.middleware.auth import extract_identity
    from src.config.settings import AppSettings, RuntimeSettings

    app = create_app()
    mock_req = MagicMock()
    mock_req.headers = {"Authorization": "Bearer   "}
    mock_req.app = app
    app.state.settings = AppSettings(
        schema_version="1.0",
        environment="test",
        runtime=RuntimeSettings(
            default_provider_id="openai-test",
            allowed_provider_ids=["openai-test"],
            require_provider_healthcheck_on_start=False,
        ),
    )
    assert asyncio.run(extract_identity(mock_req)) is None


def test_extract_identity_jwt_path_requires_app_settings_for_decode() -> None:
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from src.api.middleware.auth import extract_identity

    token = _make_token(sub="jwt-path", tenant_id="t1")
    mock_req = MagicMock()
    mock_req.headers = {"Authorization": f"Bearer {token}"}
    # Explicit state without `settings` → line 61–63 (`settings is None`).
    mock_req.app = MagicMock()
    mock_req.app.state = SimpleNamespace()
    assert asyncio.run(extract_identity(mock_req)) is None


def test_extract_identity_jwt_path_requires_auth_attribute_on_settings() -> None:
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from src.api.app import create_app
    from src.api.middleware.auth import extract_identity

    token = _make_token(sub="jwt-path-2", tenant_id="t1")
    mock_req = MagicMock()
    mock_req.headers = {"Authorization": f"Bearer {token}"}
    mock_req.app = create_app()
    # Settings without `auth` → getattr(..., "auth", None) is None (lines 64–66).
    mock_req.app.state.settings = SimpleNamespace(environment="test")
    assert asyncio.run(extract_identity(mock_req)) is None


def test_extract_identity_accepts_valid_bearer_jwt_when_configured() -> None:
    import asyncio
    from unittest.mock import MagicMock

    from src.api.middleware.auth import extract_identity
    from src.config.settings import AppSettings, AuthSettings, RuntimeSettings

    from src.api.app import create_app

    token = _make_token(sub="jwt-ok", tenant_id="t1", roles=["admin"])
    mock_req = MagicMock()
    mock_req.headers = {"Authorization": f"Bearer {token}"}
    mock_req.app = create_app()
    mock_req.app.state.settings = AppSettings(
        schema_version="1.0",
        environment="test",
        runtime=RuntimeSettings(
            default_provider_id="openai-test",
            allowed_provider_ids=["openai-test"],
            require_provider_healthcheck_on_start=False,
        ),
        auth=AuthSettings(jwt_secret=_SECRET, algorithm=_ALG),
    )
    identity = asyncio.run(extract_identity(mock_req))
    assert identity is not None
    assert identity.subject == "jwt-ok"
    assert identity.token_validation_state == TokenValidationState.VALID


def test_decode_jwt_from_jwks_blank_url_returns_none() -> None:
    from src.identity.jwt_resolver import decode_jwt_from_jwks

    assert decode_jwt_from_jwks("tok", "") is None
    assert decode_jwt_from_jwks("tok", "   ") is None


def test_decode_jwt_from_jwks_success_with_mocked_client() -> None:
    from unittest.mock import MagicMock, patch

    from src.identity.jwt_resolver import decode_jwt_from_jwks

    signing_key = MagicMock()
    signing_key.algorithm_name = "RS256"
    signing_key.key = MagicMock()
    payload = {
        "sub": "jwks-user",
        "exp": int(time.time()) + 3600,
        "tenant_id": "t-jwks",
        "roles": ["viewer"],
    }
    with patch("src.identity.jwt_resolver.PyJWKClient") as mock_cls:
        mock_cls.return_value.get_signing_key_from_jwt.return_value = signing_key
        with patch("src.identity.jwt_resolver.jwt.decode", return_value=payload):
            identity = decode_jwt_from_jwks("header.payload.sig", "https://issuer/jwks.json")
    assert identity is not None
    assert identity.subject == "jwks-user"
    assert identity.tenant_id == "t-jwks"
    assert identity.roles == ["viewer"]
    assert identity.token_validation_state == TokenValidationState.VALID


def test_decode_jwt_from_jwks_expired_returns_expired_identity() -> None:
    from unittest.mock import MagicMock, patch

    from src.identity.jwt_resolver import decode_jwt_from_jwks

    signing_key = MagicMock()
    signing_key.algorithm_name = "RS256"
    signing_key.key = MagicMock()
    with patch("src.identity.jwt_resolver.PyJWKClient") as mock_cls:
        mock_cls.return_value.get_signing_key_from_jwt.return_value = signing_key
        with patch(
            "src.identity.jwt_resolver.jwt.decode",
            side_effect=jwt.ExpiredSignatureError("expired"),
        ):
            identity = decode_jwt_from_jwks("tok", "https://issuer/jwks.json")
    assert identity is not None
    assert identity.token_validation_state == TokenValidationState.EXPIRED


def test_decode_jwt_from_jwks_client_failure_returns_none() -> None:
    from unittest.mock import patch

    from src.identity.jwt_resolver import decode_jwt_from_jwks

    with patch("src.identity.jwt_resolver.PyJWKClient", side_effect=RuntimeError("jwks down")):
        assert decode_jwt_from_jwks("tok", "https://issuer/jwks.json") is None


def test_extract_identity_uses_jwks_when_configured() -> None:
    import asyncio
    from unittest.mock import MagicMock, patch

    from src.api.app import create_app
    from src.api.middleware.auth import extract_identity
    from src.config.settings import AppSettings, AuthSettings, RuntimeSettings

    mock_req = MagicMock()
    mock_req.headers = {"Authorization": "Bearer any-token"}
    mock_req.app = create_app()
    mock_req.app.state.settings = AppSettings(
        schema_version="1.0",
        environment="test",
        runtime=RuntimeSettings(
            default_provider_id="openai-test",
            allowed_provider_ids=["openai-test"],
            require_provider_healthcheck_on_start=False,
        ),
        auth=AuthSettings(jwt_secret="", jwks_url="https://issuer/jwks.json", algorithm="RS256"),
    )
    stub = IdentityContext(
        subject="from-jwks",
        tenant_id="t1",
        roles=[],
        token_validation_state=TokenValidationState.VALID,
    )
    with patch("src.identity.jwt_resolver.decode_jwt_from_jwks", return_value=stub):
        identity = asyncio.run(extract_identity(mock_req))
    assert identity is not None
    assert identity.subject == "from-jwks"


def test_jwt_and_x_identity_precedence() -> None:
    """Authorization: Bearer JWT takes precedence over X-Identity header."""
    from fastapi.testclient import TestClient

    app = _build_jwt_app(_SECRET)
    token = _make_token(sub="jwt-user", tenant_id="jwt-tenant", roles=["jwt-role"])
    with TestClient(app) as client:
        resp = client.get(
            "/health",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Identity": json.dumps({
                    "subject": "identity-user",
                    "tenant_id": "identity-tenant",
                    "token_validation_state": "valid",
                }),
            },
        )
    assert resp.status_code == 200
