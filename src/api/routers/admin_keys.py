"""
File: admin_keys.py
Path: src/api/routers/admin_keys.py
Role: API key management endpoints — create, list, and revoke API keys.
Used By:
 - src/api/app.py
Depends On:
 - src/api/dependencies.py
 - src/api/schemas/auth_schemas.py
 - src/persistence/contracts.py
Notes:
 - POST /admin/keys creates a new key and returns the plaintext once — never stored.
 - DELETE /admin/keys/{key_id} hard-deletes the key record; revoked immediately.
 - All endpoints require require_valid_identity (API key, JWT, or X-Identity in test mode).
 - Key format: 'exo_<32 random hex chars>'.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from src.api.dependencies import require_valid_identity
from src.api.schemas.auth_schemas import (
    ApiKeyCreateRequest,
    ApiKeyCreateResponse,
    ApiKeyInfo,
    ApiKeyListResponse,
)
from src.identity.contracts import IdentityContext
from src.persistence.contracts import ApiKeyRecord, ApiKeyStore

router = APIRouter(tags=["admin-keys"])


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def _record_to_info(record: ApiKeyRecord) -> ApiKeyInfo:
    return ApiKeyInfo(
        key_id=record.key_id,
        tenant_id=record.tenant_id,
        subject=record.subject,
        roles=record.roles,
        description=record.description,
        enabled=record.enabled,
        created_at=record.created_at,
    )


@router.post("/admin/keys", status_code=201, response_model=ApiKeyCreateResponse)
async def create_api_key(
    body: ApiKeyCreateRequest,
    request: Request,
    _identity: IdentityContext = Depends(require_valid_identity),
) -> ApiKeyCreateResponse:
    """Create a new API key.

    The plaintext key is returned once in the response and never stored.
    Store it securely — it cannot be retrieved again.
    """
    store: ApiKeyStore | None = getattr(request.app.state, "api_key_store", None)
    if store is None:
        raise HTTPException(
            status_code=503,
            detail="API key store is not configured on this server.",
        )

    raw_key = "exo_" + secrets.token_hex(32)
    key_id = secrets.token_hex(16)
    created_at = datetime.now(tz=timezone.utc).isoformat()

    record = ApiKeyRecord(
        key_id=key_id,
        tenant_id=body.tenant_id,
        subject=body.subject,
        key_hash=_hash_key(raw_key),
        roles=body.roles,
        description=body.description,
        enabled=True,
        created_at=created_at,
    )
    await store.save_key(record)

    return ApiKeyCreateResponse(
        key_id=key_id,
        key=raw_key,
        tenant_id=body.tenant_id,
        subject=body.subject,
        roles=body.roles,
        description=body.description,
        created_at=created_at,
    )


@router.get("/admin/keys", response_model=ApiKeyListResponse)
async def list_api_keys(
    request: Request,
    tenant_id: str | None = None,
    _identity: IdentityContext = Depends(require_valid_identity),
) -> ApiKeyListResponse:
    """List API key metadata.

    Optionally filter by tenant_id query parameter.
    Key hashes are never included in the response.
    """
    store: ApiKeyStore | None = getattr(request.app.state, "api_key_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="API key store is not configured.")
    records = await store.list_keys(tenant_id=tenant_id)
    return ApiKeyListResponse(
        keys=[_record_to_info(r) for r in records],
        total=len(records),
    )


@router.delete("/admin/keys/{key_id}", status_code=204)
async def delete_api_key(
    key_id: str,
    request: Request,
    _identity: IdentityContext = Depends(require_valid_identity),
) -> None:
    """Revoke an API key by key_id.

    The key is immediately deleted — any in-flight requests using it will fail
    on the next auth check.
    """
    store: ApiKeyStore | None = getattr(request.app.state, "api_key_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="API key store is not configured.")
    existing = await store.get_key(key_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"API key '{key_id}' not found.")
    await store.delete_key(key_id)
