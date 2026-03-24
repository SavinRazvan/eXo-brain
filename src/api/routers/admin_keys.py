"""
File: admin_keys.py
Path: src/api/routers/admin_keys.py
Role: API key management endpoints delegated to the identity-access module service.
Used By:
 - src/api/app.py
Depends On:
 - src/api/dependencies.py
 - src/api/schemas/auth_schemas.py
 - src/modules/identity_access/service.py
Notes:
 - POST /admin/keys creates a new key and returns the plaintext once — never stored.
 - DELETE /admin/keys/{key_id} hard-deletes the key record; revoked immediately.
 - All endpoints require explicit platform-admin authorization via the identity-access module.
 - Key format: 'exo_<32 random hex chars>'.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from src.api.dependencies import get_app_modules, require_valid_identity
from src.api.schemas.auth_schemas import (
    ApiKeyCreateRequest,
    ApiKeyCreateResponse,
    ApiKeyInfo,
    ApiKeyListResponse,
)
from src.identity.contracts import IdentityContext
from src.modules.identity_access.service import IdentityAccessError

router = APIRouter(tags=["admin-keys"])


def _record_to_info(record) -> ApiKeyInfo:
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
    identity: IdentityContext = Depends(require_valid_identity),
) -> ApiKeyCreateResponse:
    """Create a new API key.

    The plaintext key is returned once in the response and never stored.
    Store it securely — it cannot be retrieved again.
    """
    modules = get_app_modules(request)
    service = modules.identity_access.service if modules is not None else None
    if service is None:
        raise HTTPException(status_code=503, detail="Identity access module is not configured.")
    try:
        record, raw_key = await service.create_api_key(
            identity=identity,
            tenant_id=body.tenant_id,
            subject=body.subject,
            roles=body.roles,
            description=body.description,
        )
    except IdentityAccessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return ApiKeyCreateResponse(
        key_id=record.key_id,
        key=raw_key,
        tenant_id=record.tenant_id,
        subject=record.subject,
        roles=record.roles,
        description=record.description,
        created_at=record.created_at,
    )


@router.get("/admin/keys", response_model=ApiKeyListResponse)
async def list_api_keys(
    request: Request,
    tenant_id: str | None = None,
    identity: IdentityContext = Depends(require_valid_identity),
) -> ApiKeyListResponse:
    """List API key metadata.

    Optionally filter by tenant_id query parameter.
    Key hashes are never included in the response.
    """
    modules = get_app_modules(request)
    service = modules.identity_access.service if modules is not None else None
    if service is None:
        raise HTTPException(status_code=503, detail="Identity access module is not configured.")
    try:
        records = await service.list_api_keys(identity=identity, requested_tenant_id=tenant_id)
    except IdentityAccessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return ApiKeyListResponse(
        keys=[_record_to_info(r) for r in records],
        total=len(records),
    )


@router.delete("/admin/keys/{key_id}", status_code=204)
async def delete_api_key(
    key_id: str,
    request: Request,
    identity: IdentityContext = Depends(require_valid_identity),
) -> None:
    """Revoke an API key by key_id.

    The key is immediately deleted — any in-flight requests using it will fail
    on the next auth check.
    """
    modules = get_app_modules(request)
    service = modules.identity_access.service if modules is not None else None
    if service is None:
        raise HTTPException(status_code=503, detail="Identity access module is not configured.")
    try:
        await service.delete_api_key(identity=identity, key_id=key_id)
    except IdentityAccessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
