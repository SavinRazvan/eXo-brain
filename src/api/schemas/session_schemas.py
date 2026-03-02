"""
File: session_schemas.py
Path: src/api/schemas/session_schemas.py
Role: Pydantic request/response schemas for session lifecycle endpoints.
Used By:
 - src/api/routers/sessions.py
Depends On:
 - pydantic
Notes:
 - correlation_id is optional — callers may supply their own for distributed tracing.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SessionCreateRequest(BaseModel):
    agent_id: str = Field(..., description="Registered agent to bind this session to")
    provider_id: str = Field(..., description="Registered provider adapter to use (e.g. 'openai-gpt4o-mini')")
    correlation_id: str = Field(default="", description="Optional caller-supplied correlation ID for tracing")


class SessionCreateResponse(BaseModel):
    session_id: str
    tenant_id: str
    agent_id: str
    provider_id: str
    correlation_id: str


class SessionStateResponse(BaseModel):
    session_id: str
    tenant_id: str
    agent_id: str
    provider_id: str
    correlation_id: str
    created_at: str = ""
