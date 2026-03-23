"""
File: auth.py
Path: src/api/middleware/auth.py
Role: Resolve IdentityContext from the request using multi-mode authentication.
Used By:
 - src/api/dependencies.py
Depends On:
 - src/identity/contracts.py
 - src/identity/resolver.py
 - src/identity/jwt_resolver.py
 - src/persistence/contracts.py
Notes:
 - Auth precedence (D6): Authorization: Bearer > X-API-Key > X-Identity (test/dev only).
 - Bearer token: tried as JWT first (when jwt_secret configured); falls back to API-key lookup.
 - X-Identity plain-JSON: allowed only when environment is 'test' or 'development' (D2).
 - Returns None if no valid identity can be resolved; callers raise 401.
 - extract_identity is async because API-key store lookups are async.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from starlette.requests import HTTPConnection

from src.identity.contracts import IdentityContext, TokenValidationState
from src.modules.platform_bootstrap.service import app_modules_from_requestlike
from src.identity.resolver import resolve_identity

_X_IDENTITY_HEADER = "X-Identity"
_TEST_ENVIRONMENTS = {"test", "development"}


def _hash_key(raw_key: str) -> str:
    """Return the SHA-256 hex digest of the raw API key."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


async def _resolve_from_api_key(raw_key: str, request: HTTPConnection) -> IdentityContext | None:
    """Look up raw_key in the ApiKeyStore and return an IdentityContext, or None."""
    from src.persistence.contracts import ApiKeyStore

    modules = app_modules_from_requestlike(request)
    api_key_store = modules.identity_access.service.api_key_store if modules is not None else None
    if not isinstance(api_key_store, ApiKeyStore):
        return None
    record = await api_key_store.lookup_by_hash(_hash_key(raw_key))
    if record is None or not record.enabled:
        return None
    return IdentityContext(
        subject=record.subject,
        tenant_id=record.tenant_id,
        roles=record.roles,
        token_id=record.key_id,
        token_validation_state=TokenValidationState.VALID,
    )


def _resolve_from_jwt(token: str, request: HTTPConnection) -> IdentityContext | None:
    """Try to decode token as a JWT using configured AuthSettings."""
    modules = app_modules_from_requestlike(request)
    settings = modules.platform_bootstrap.settings if modules is not None else None
    if settings is None:
        return None
    auth_cfg = getattr(settings, "auth", None)
    if auth_cfg is None:
        return None
    if not auth_cfg.jwt_secret and not auth_cfg.jwks_url:
        return None

    from src.identity.jwt_resolver import decode_jwt, decode_jwt_from_jwks

    jwks_url = str(getattr(auth_cfg, "jwks_url", "") or "").strip()
    if jwks_url:
        return decode_jwt_from_jwks(token, jwks_url)
    return decode_jwt(token, secret=auth_cfg.jwt_secret, algorithm=auth_cfg.algorithm)


async def extract_identity(request: HTTPConnection) -> IdentityContext | None:
    """Resolve IdentityContext from the request.

    Precedence:
    1. Authorization: Bearer <token>  — JWT (if configured) then API-key
    2. X-API-Key: <key>               — API-key lookup
    3. X-Identity: <json>             — plain-JSON (test/development environment only)
    """
    modules = app_modules_from_requestlike(request)
    settings = modules.platform_bootstrap.settings if modules is not None else None
    environment = getattr(settings, "environment", "test") if settings else "test"

    # -- 1. Authorization: Bearer -------------------------------------------
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        if not token:
            return None

        # Try JWT first
        jwt_identity = _resolve_from_jwt(token, request)
        if jwt_identity is not None:
            # EXPIRED state: return it so caller produces a useful 401 message
            if jwt_identity.token_validation_state == TokenValidationState.EXPIRED:
                return jwt_identity
            if jwt_identity.token_validation_state == TokenValidationState.VALID:
                return jwt_identity

        # Fall back to API-key lookup
        api_key_identity = await _resolve_from_api_key(token, request)
        if api_key_identity is not None:
            return api_key_identity

        # Bearer token present but unresolved → explicit None (not fall through to X-Identity)
        return None

    # -- 2. X-API-Key header ------------------------------------------------
    raw_api_key = request.headers.get("X-API-Key", "").strip()
    if raw_api_key:
        return await _resolve_from_api_key(raw_api_key, request)

    # -- 3. X-Identity (test / development only) ----------------------------
    if environment in _TEST_ENVIRONMENTS:
        raw_header = request.headers.get(_X_IDENTITY_HEADER)
        if not raw_header:
            return None
        try:
            payload: Any = json.loads(raw_header)
        except json.JSONDecodeError:
            return None
        return resolve_identity(payload)

    return None


def is_identity_usable(identity: IdentityContext) -> bool:
    """Return True only for VALID or UNKNOWN token states.

    INVALID and EXPIRED are explicitly rejected.
    ROTATION_REQUIRED is allowed through — callers are warned but not blocked.
    """
    rejected = {TokenValidationState.INVALID, TokenValidationState.EXPIRED}
    return identity.token_validation_state not in rejected
