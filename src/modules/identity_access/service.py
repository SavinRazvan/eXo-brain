"""
File: service.py
Path: src/modules/identity_access/service.py
Role: Public module services for platform-admin authorization and API-key administration.
Used By:
 - src/modules/platform_bootstrap/service.py
 - src/api/dependencies.py
 - src/api/routers/admin_keys.py
 - src/api/routers/providers.py
Depends On:
 - src.identity/contracts.py
 - src.persistence/contracts.py
Notes:
 - `/admin/*` surfaces must use explicit platform-admin checks rather than generic authentication.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import secrets

from src.identity.contracts import IdentityContext
from src.persistence.contracts import ApiKeyRecord, ApiKeyStore


PLATFORM_ADMIN_ROLES = frozenset({"platform_admin", "super_admin"})


@dataclass(frozen=True, slots=True)
class IdentityAccessError(Exception):
    status_code: int
    detail: str

    def __str__(self) -> str:
        return self.detail


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


@dataclass(slots=True)
class IdentityAccessService:
    api_key_store: ApiKeyStore | None
    allow_cross_tenant_admin: bool = False
    cross_tenant_admin_roles: tuple[str, ...] = ("super_admin",)

    def is_platform_admin(self, identity: IdentityContext) -> bool:
        return any(str(role).strip() in PLATFORM_ADMIN_ROLES for role in identity.roles)

    def require_platform_admin(self, identity: IdentityContext, *, surface: str) -> None:
        if self.is_platform_admin(identity):
            return
        raise IdentityAccessError(
            status_code=403,
            detail=(
                f"PLATFORM_ADMIN_REQUIRED: '{surface}' requires one of the platform admin roles "
                f"{sorted(PLATFORM_ADMIN_ROLES)}."
            ),
        )

    def allow_cross_tenant_admin_access(self, identity: IdentityContext) -> bool:
        if not self.allow_cross_tenant_admin:
            return False
        allowed_roles = {str(role).strip() for role in self.cross_tenant_admin_roles if str(role).strip()}
        return any(str(role).strip() in allowed_roles for role in identity.roles)

    def scoped_tenant_id(
        self,
        *,
        identity: IdentityContext,
        requested_tenant_id: str | None,
    ) -> str | None:
        normalized_requested = str(requested_tenant_id or "").strip()
        normalized_identity_tenant = str(identity.tenant_id or "").strip()
        if normalized_requested:
            if normalized_requested == normalized_identity_tenant:
                return normalized_requested
            self.require_platform_admin(identity, surface="tenant_scope_override")
            return normalized_requested
        return normalized_identity_tenant or None

    def _require_api_key_store(self) -> ApiKeyStore:
        if self.api_key_store is None:
            raise IdentityAccessError(
                status_code=503,
                detail="API key store is not configured on this server.",
            )
        return self.api_key_store

    async def create_api_key(
        self,
        *,
        identity: IdentityContext,
        tenant_id: str,
        subject: str,
        roles: list[str],
        description: str,
    ) -> tuple[ApiKeyRecord, str]:
        self.require_platform_admin(identity, surface="admin/keys:create")
        store = self._require_api_key_store()
        normalized_tenant_id = str(tenant_id or "").strip()
        if not normalized_tenant_id:
            raise IdentityAccessError(status_code=422, detail="tenant_id is required.")

        raw_key = "exo_" + secrets.token_hex(32)
        record = ApiKeyRecord(
            key_id=secrets.token_hex(16),
            tenant_id=normalized_tenant_id,
            subject=subject,
            key_hash=_hash_key(raw_key),
            roles=[str(role).strip() for role in roles if str(role).strip()],
            description=description,
            enabled=True,
            created_at=_utc_now(),
        )
        await store.save_key(record)
        return record, raw_key

    async def list_api_keys(
        self,
        *,
        identity: IdentityContext,
        requested_tenant_id: str | None = None,
    ) -> list[ApiKeyRecord]:
        self.require_platform_admin(identity, surface="admin/keys:list")
        store = self._require_api_key_store()
        effective_tenant_id = self.scoped_tenant_id(
            identity=identity,
            requested_tenant_id=requested_tenant_id,
        )
        return await store.list_keys(tenant_id=effective_tenant_id)

    async def delete_api_key(
        self,
        *,
        identity: IdentityContext,
        key_id: str,
    ) -> ApiKeyRecord:
        self.require_platform_admin(identity, surface="admin/keys:delete")
        store = self._require_api_key_store()
        existing = await store.get_key(key_id)
        if existing is None:
            raise IdentityAccessError(status_code=404, detail=f"API key '{key_id}' not found.")
        await store.delete_key(key_id)
        return existing


@dataclass(slots=True)
class IdentityAccessModule:
    service: IdentityAccessService
