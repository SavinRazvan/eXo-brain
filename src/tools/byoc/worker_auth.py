"""
File: worker_auth.py
Path: src/tools/byoc/worker_auth.py
Role: Sign and verify short-lived JWTs used by BYOC pull workers.
Used By:
 - src/tools/byoc/connector_runtime.py
 - src/api/routers/runtime_control.py
Depends On:
 - datetime
 - jwt
Notes:
 - Tokens are tenant-scoped and meant for service-to-service worker authentication.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import uuid

import jwt


@dataclass(slots=True)
class WorkerAuthClaims:
    tenant_id: str
    worker_id: str
    token_id: str
    issued_at_epoch: int
    expires_at_epoch: int


def mint_worker_token(
    *,
    tenant_id: str,
    worker_id: str,
    secret: str,
    ttl_seconds: int = 300,
) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(seconds=max(int(ttl_seconds), 1))
    payload = {
        "sub": f"byoc-worker:{worker_id}",
        "tenant_id": tenant_id,
        "worker_id": worker_id,
        "jti": f"jti_{uuid.uuid4().hex[:16]}",
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return str(jwt.encode(payload, secret, algorithm="HS256"))


def verify_worker_token(
    *,
    token: str,
    secret: str,
    expected_tenant_id: str,
) -> WorkerAuthClaims:
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={"require": ["sub", "tenant_id", "worker_id", "jti", "iat", "exp"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise ValueError("WORKER_TOKEN_EXPIRED") from exc
    except jwt.InvalidTokenError as exc:
        raise ValueError("WORKER_TOKEN_INVALID") from exc

    tenant_id = str(payload.get("tenant_id", "")).strip()
    if tenant_id != expected_tenant_id:
        raise ValueError("WORKER_TOKEN_TENANT_MISMATCH")
    worker_id = str(payload.get("worker_id", "")).strip()
    if not worker_id:
        raise ValueError("WORKER_TOKEN_INVALID")
    token_id = str(payload.get("jti", "")).strip()
    if not token_id:
        raise ValueError("WORKER_TOKEN_INVALID")
    return WorkerAuthClaims(
        tenant_id=tenant_id,
        worker_id=worker_id,
        token_id=token_id,
        issued_at_epoch=int(payload.get("iat", 0)),
        expires_at_epoch=int(payload.get("exp", 0)),
    )

