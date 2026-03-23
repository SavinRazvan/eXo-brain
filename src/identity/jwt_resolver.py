"""
File: jwt_resolver.py
Path: src/identity/jwt_resolver.py
Role: Decode and validate JWT Bearer tokens, returning an IdentityContext.
Used By:
 - src/api/middleware/auth.py
Depends On:
 - src/identity/contracts.py
 - PyJWT
 Notes:
 - Supports HS256/HS384/HS512 (symmetric secret) and asymmetric algorithms via JWKS URL (PyJWKClient).
 - Returns EXPIRED identity (not None) on expired tokens so callers can return 401 with reason.
 - Returns None on structurally invalid tokens (wrong format, bad signature, unknown algorithm).
 - Expected JWT claims: sub, tenant_id, roles (list[str]), exp, iat.
"""

from __future__ import annotations

import logging

import jwt
from jwt import PyJWKClient

from src.identity.contracts import IdentityContext, TokenValidationState

logger = logging.getLogger(__name__)

_SYMMETRIC_ALGORITHMS = {"HS256", "HS384", "HS512"}
_ASYMMETRIC_ALGORITHMS = {"RS256", "RS384", "RS512", "ES256", "ES384", "ES512"}


def decode_jwt(
    token: str,
    secret: str,
    algorithm: str = "HS256",
) -> IdentityContext | None:
    """Decode and verify a JWT, returning an IdentityContext.

    Returns:
        IdentityContext with EXPIRED state if the token is expired.
        IdentityContext with VALID state on success.
        None if the token is structurally invalid or signature verification fails.
    """
    if not secret and algorithm in _SYMMETRIC_ALGORITHMS:
        logger.warning("JWT decode skipped: no jwt_secret configured for algorithm %s", algorithm)
        return None

    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[algorithm],
            options={"require": ["sub", "exp"]},
        )
    except jwt.ExpiredSignatureError:
        return IdentityContext(
            subject="",
            token_validation_state=TokenValidationState.EXPIRED,
        )
    except jwt.InvalidTokenError as exc:
        logger.debug("JWT decode failed: %s", exc)
        return None

    return _identity_from_payload(payload)


def _identity_from_payload(payload: dict) -> IdentityContext | None:
    subject = str(payload.get("sub", "")).strip()
    if not subject:
        return None
    tenant_id = str(payload.get("tenant_id", "default")).strip() or "default"
    roles_raw = payload.get("roles", [])
    roles = [str(r).strip() for r in roles_raw if str(r).strip()] if isinstance(roles_raw, list) else []
    token_id = str(payload.get("jti", "")).strip()
    issued_at = str(payload.get("iat", ""))
    expires_at = str(payload.get("exp", ""))
    return IdentityContext(
        subject=subject,
        tenant_id=tenant_id,
        roles=roles,
        token_id=token_id,
        token_validation_state=TokenValidationState.VALID,
        token_issued_at_utc=issued_at,
        token_expires_at_utc=expires_at,
    )


def decode_jwt_from_jwks(token: str, jwks_url: str) -> IdentityContext | None:
    """Verify a JWT against a remote JWKS endpoint (OIDC-style asymmetric keys)."""
    url = str(jwks_url or "").strip()
    if not url:
        return None
    try:
        jwks_client = PyJWKClient(url, cache_keys=True, timeout=10)
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        alg_name = str(getattr(signing_key, "algorithm_name", "") or "").strip().upper()
        algorithms = [alg_name] if alg_name in _ASYMMETRIC_ALGORITHMS else sorted(_ASYMMETRIC_ALGORITHMS)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=algorithms,
            options={"require": ["sub", "exp"]},
        )
    except jwt.ExpiredSignatureError:
        return IdentityContext(
            subject="",
            token_validation_state=TokenValidationState.EXPIRED,
        )
    except Exception as exc:  # noqa: BLE001 — JWKS/network/JWT errors collapse to unauthenticated
        logger.debug("JWKS JWT decode failed: %s", exc)
        return None
    return _identity_from_payload(payload)
