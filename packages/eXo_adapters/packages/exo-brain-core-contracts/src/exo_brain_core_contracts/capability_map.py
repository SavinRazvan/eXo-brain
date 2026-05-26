"""
File: capability_map.py
Path: packages/exo-brain-core-contracts/src/exo_brain_core_contracts/capability_map.py
Role: Provider capability and health contracts for runtime adapters.
Used By:
 - packages/exo-brain-core-contracts/src/exo_brain_core_contracts/runtime_adapter.py
 - src/runtime/capability_map.py (control-plane re-export)
Depends On:
 - dataclasses
 - enum
Notes:
 - Keep provider-neutral and dependency-light for package consumers.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SecurityTier(str, Enum):
    MANAGED_VENDOR = "managed_vendor"
    SELF_MANAGED = "self_managed"
    LOCAL_ONLY = "local_only"


class HealthState(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"


@dataclass(slots=True)
class ProviderCapabilityMap:
    provider_id: str
    supports_agents_sdk_native: bool = False
    supports_openai_compatible_api: bool = False
    supports_streaming: bool = True
    supports_function_calling: bool = True
    supports_structured_output: bool = True
    supports_handoffs: bool = False
    max_context_tokens: int = 128000
    reliability_score: int = 3
    security_tier: SecurityTier = SecurityTier.MANAGED_VENDOR
    recommended_runtime_mode: str = "hybrid"

    def should_force_deterministic(self) -> bool:
        return (
            not self.supports_function_calling
            or not self.supports_structured_output
            or self.reliability_score < 4
        )


@dataclass(slots=True)
class HealthStatus:
    state: HealthState
    reason: str = ""
