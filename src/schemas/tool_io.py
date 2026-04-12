"""
File: tool_io.py
Path: src/schemas/tool_io.py
Role: Re-export published tool-call, policy, and result envelopes for control-plane parity with adapter packages.
Used By:
 - src/tools/executor.py
 - src/runtime/mode_selector.py
 - src/core/orchestrator.py
Depends On:
 - exo_brain_core_contracts.tool_io
Notes:
 - Canonical types: distribution ``exo-brain-core-contracts`` (**eXo_adapters**). Import from ``src.schemas.tool_io`` keeps shared-kernel paths stable; symbols match the package.
"""

from __future__ import annotations

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
    "NormalizedError",
    "PolicyAction",
    "PolicyAudit",
    "PolicyDecision",
    "RiskTier",
    "ToolAudit",
    "ToolCallContext",
    "ToolExecutionMode",
    "ToolResult",
    "ToolStatus",
    "blocked_result",
]
