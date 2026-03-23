"""
File: test_identity_access_service.py
Path: tests/modules/identity_access/test_identity_access_service.py
Role: Unit tests for the identity-access module service contracts.
Used By:
 - pytest
Depends On:
 - src/modules/identity_access/service.py
 - src/identity/contracts.py
Notes:
 - Covers platform-admin enforcement and tenant scoping without going through HTTP routers.
"""

from __future__ import annotations

import pytest

from src.identity.contracts import IdentityContext, TokenValidationState
from src.modules.identity_access.service import IdentityAccessError, IdentityAccessService
from src.persistence.contracts import ApiKeyRecord


class _MemoryApiKeyStore:
    def __init__(self) -> None:
        self._records: dict[str, ApiKeyRecord] = {}

    async def save_key(self, record: ApiKeyRecord) -> None:
        self._records[record.key_id] = record

    async def get_key(self, key_id: str) -> ApiKeyRecord | None:
        return self._records.get(key_id)

    async def lookup_by_hash(self, key_hash: str) -> ApiKeyRecord | None:
        for record in self._records.values():
            if record.key_hash == key_hash and record.enabled:
                return record
        return None

    async def delete_key(self, key_id: str) -> None:
        self._records.pop(key_id, None)

    async def list_keys(self, tenant_id: str | None = None) -> list[ApiKeyRecord]:
        records = list(self._records.values())
        if tenant_id is not None:
            records = [record for record in records if record.tenant_id == tenant_id]
        return sorted(records, key=lambda record: record.key_id)


def _identity(*roles: str, tenant_id: str = "tenant-a") -> IdentityContext:
    return IdentityContext(
        subject="user@example.com",
        tenant_id=tenant_id,
        roles=list(roles),
        token_validation_state=TokenValidationState.VALID,
    )


@pytest.mark.asyncio
async def test_create_api_key_requires_platform_admin_role() -> None:
    service = IdentityAccessService(api_key_store=_MemoryApiKeyStore())

    with pytest.raises(IdentityAccessError, match="PLATFORM_ADMIN_REQUIRED"):
        await service.create_api_key(
            identity=_identity("admin"),
            tenant_id="tenant-a",
            subject="svc@example.com",
            roles=["reader"],
            description="demo",
        )


@pytest.mark.asyncio
async def test_list_api_keys_scopes_to_requested_tenant_for_platform_admin() -> None:
    store = _MemoryApiKeyStore()
    service = IdentityAccessService(api_key_store=store)
    await store.save_key(
        ApiKeyRecord(
            key_id="a1",
            tenant_id="tenant-a",
            subject="a@example.com",
            key_hash="hash-a",
            roles=["reader"],
        )
    )
    await store.save_key(
        ApiKeyRecord(
            key_id="b1",
            tenant_id="tenant-b",
            subject="b@example.com",
            key_hash="hash-b",
            roles=["reader"],
        )
    )

    default_scoped = await service.list_api_keys(identity=_identity("platform_admin", tenant_id="tenant-a"))
    override_scoped = await service.list_api_keys(
        identity=_identity("platform_admin", tenant_id="tenant-a"),
        requested_tenant_id="tenant-b",
    )

    assert [record.key_id for record in default_scoped] == ["a1"]
    assert [record.key_id for record in override_scoped] == ["b1"]


def test_identity_access_error_str_returns_detail() -> None:
    assert str(IdentityAccessError(status_code=422, detail="detail-text")) == "detail-text"


@pytest.mark.asyncio
async def test_create_api_key_requires_tenant_id_and_configured_store() -> None:
    service = IdentityAccessService(api_key_store=None)

    with pytest.raises(IdentityAccessError, match="API key store is not configured"):
        await service.create_api_key(
            identity=_identity("platform_admin"),
            tenant_id="tenant-a",
            subject="svc@example.com",
            roles=["reader"],
            description="demo",
        )

    service = IdentityAccessService(api_key_store=_MemoryApiKeyStore())
    with pytest.raises(IdentityAccessError, match="tenant_id is required"):
        await service.create_api_key(
            identity=_identity("platform_admin"),
            tenant_id="",
            subject="svc@example.com",
            roles=["reader"],
            description="demo",
        )
