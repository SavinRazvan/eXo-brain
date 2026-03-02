"""
File: agent_schemas.py
Path: src/api/schemas/agent_schemas.py
Role: Pydantic request/response schemas for agent registration and management endpoints.
Used By:
 - src/api/routers/agents.py
Depends On:
 - pydantic
 - src/agents/contracts.py
Notes:
 - capability_tags maps to AgentCapabilityTag enum values.
 - metadata is a free-form dict for adapter-specific extras (model, temperature overrides, etc.).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AgentRegisterRequest(BaseModel):
    agent_id: str = Field(..., description="Unique agent identifier within the tenant")
    role: str = Field(..., description="Functional role label — must be unique per tenant")
    capability_tags: list[str] = Field(
        default_factory=list,
        description="List of capability tag values (e.g. 'tool_use', 'retrieval')",
    )
    instructions: str = Field(default="", description="System prompt / instructions for the agent")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Adapter-specific extras — e.g. {'model': 'gpt-4o', 'temperature': 0.2}",
    )


class AgentResponse(BaseModel):
    agent_id: str
    role: str
    capability_tags: list[str]
    instructions: str
    metadata: dict[str, Any]


class AgentListResponse(BaseModel):
    agents: list[AgentResponse]
    total: int


class HandoffRouteRequest(BaseModel):
    source_role: str
    target_role: str
    reason: str = Field(default="")
    required_target_capabilities: list[str] = Field(default_factory=list)


class HandoffRouteResponse(BaseModel):
    source_role: str
    target_role: str
    reason: str
    required_target_capabilities: list[str]


class HandoffFallbackPolicyRequest(BaseModel):
    source_role: str
    target_role: str
    fallback_target_roles: list[str] = Field(default_factory=list)
    target_role_priorities: dict[str, int] = Field(default_factory=dict)


class HandoffFallbackPolicyResponse(BaseModel):
    source_role: str
    target_role: str
    fallback_target_roles: list[str]
    target_role_priorities: dict[str, int]
