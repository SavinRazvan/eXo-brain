"""
File: __init__.py
Path: packages/exo-brain-core-contracts/src/exo_brain_core_contracts/__init__.py
Role: Public exports for the core contracts package.
Used By:
 - adapter SDK package
 - provider adapter packages
Depends On:
 - sibling contract modules
Notes:
 - Keep export list explicit and stable for contract consumers.
"""

from exo_brain_core_contracts.capability_map import (
    HealthState,
    HealthStatus,
    ProviderCapabilityMap,
    SecurityTier,
)
from exo_brain_core_contracts.events import RuntimeEvent, RuntimeEventType
from exo_brain_core_contracts.runtime_adapter import RuntimeAdapter, SessionHandle
from exo_brain_core_contracts.tool_io import (
    ExecutionMetadata,
    NormalizedError,
    PolicyAction,
    PolicyAudit,
    PolicyDecision,
    RiskTier,
    ToolAudit,
    ToolCallContext,
    ToolExecutionMode,
    ToolResult,
    ToolStatus,
    blocked_result,
)

__all__ = [
    "ExecutionMetadata",
    "HealthState",
    "HealthStatus",
    "NormalizedError",
    "PolicyAction",
    "PolicyAudit",
    "PolicyDecision",
    "ProviderCapabilityMap",
    "RiskTier",
    "RuntimeAdapter",
    "RuntimeEvent",
    "RuntimeEventType",
    "SecurityTier",
    "SessionHandle",
    "ToolAudit",
    "ToolCallContext",
    "ToolExecutionMode",
    "ToolResult",
    "ToolStatus",
    "blocked_result",
]
