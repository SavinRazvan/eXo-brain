"""
File: auth_schemas.py
Path: src/api/schemas/auth_schemas.py
Role: Request and response schemas for API key management endpoints.
Used By:
 - src/api/routers/admin_keys.py
Depends On:
 - pydantic
Notes:
 - ApiKeyCreateResponse includes the plaintext key (shown once at creation, never again).
 - ApiKeyInfo omits key_hash — never expose the hash to clients.
"""

from __future__ import annotations

from pydantic import BaseModel


class ApiKeyCreateRequest(BaseModel):
    tenant_id: str
    subject: str
    roles: list[str] = []
    description: str = ""


class ApiKeyCreateResponse(BaseModel):
    key_id: str
    key: str
    tenant_id: str
    subject: str
    roles: list[str]
    description: str
    created_at: str


class ApiKeyInfo(BaseModel):
    key_id: str
    tenant_id: str
    subject: str
    roles: list[str]
    description: str
    enabled: bool
    created_at: str


class ApiKeyListResponse(BaseModel):
    keys: list[ApiKeyInfo]
    total: int
