"""
File: provider_schemas.py
Path: src/api/schemas/provider_schemas.py
Role: Pydantic response schemas for provider health and capability endpoints.
Used By:
 - src/api/routers/providers.py
Depends On:
 - pydantic
 - src/runtime/capability_map.py
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ProviderSummaryResponse(BaseModel):
    provider_id: str
    display_name: str
    enabled: bool
    profile: str
    recommended_runtime_mode: str = ""


class ProviderListResponse(BaseModel):
    providers: list[ProviderSummaryResponse]
    total: int


class ProviderHealthResponse(BaseModel):
    provider_id: str
    state: str
    reason: str = ""


class ProviderCapabilitiesResponse(BaseModel):
    provider_id: str
    supports_streaming: bool
    supports_function_calling: bool
    supports_structured_output: bool
    supports_handoffs: bool
    supports_agents_sdk_native: bool
    supports_openai_compatible_api: bool
    reliability_score: int
    security_tier: str
    recommended_runtime_mode: str
    extras: dict[str, Any] = {}
