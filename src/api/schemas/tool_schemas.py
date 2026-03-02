"""
File: tool_schemas.py
Path: src/api/schemas/tool_schemas.py
Role: Pydantic request/response schemas for tool registration and management endpoints.
Used By:
 - src/api/routers/tools.py
Depends On:
 - pydantic
 - src/schemas/tool_io.py
Notes:
 - handler_ref format: "module.path:function_name" — resolved via importlib at registration time.
 - parameters_schema must be a valid JSON Schema object dict.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from src.schemas.tool_io import RiskTier


class ToolRegisterRequest(BaseModel):
    name: str = Field(..., description="Unique tool name within the tenant's registry")
    handler_ref: str = Field(
        ...,
        description='Import path to the Python function: "module.path:function_name"',
        examples=["src.tools.math:calculate_result"],
    )
    description: str = Field(default="", description="Human-readable description of what the tool does")
    parameters_schema: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON Schema object describing the tool's input arguments",
    )
    risk_tier: RiskTier = Field(default=RiskTier.LOW, description="Risk classification for policy gate decisions")
    is_state_changing: bool = Field(default=False, description="True if the tool modifies external state")
    timeout_ms: int = Field(default=30000, ge=100, description="Execution timeout in milliseconds")


class ToolResponse(BaseModel):
    name: str
    description: str
    handler_ref: str
    risk_tier: RiskTier
    is_state_changing: bool
    timeout_ms: int
    parameters_schema: dict[str, Any]


class ToolListResponse(BaseModel):
    tools: list[ToolResponse]
    total: int
