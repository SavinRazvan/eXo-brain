"""
File: mode_selector.py
Path: src/runtime/mode_selector.py
Role: Runtime execution mode selection logic for provider-native vs deterministic paths.
Used By:
 - src/core/orchestrator.py
Depends On:
 - src/runtime/capability_map.py
 - src/schemas/tool_io.py
Notes:
 - Deterministic mode is the safe fallback when capabilities or policy are uncertain.
"""

from __future__ import annotations

from src.runtime.capability_map import ProviderCapabilityMap
from src.schemas.tool_io import (
    PolicyAction,
    PolicyDecision,
    RiskTier,
    ToolCallContext,
    ToolExecutionMode,
)


def select_execution_mode(
    tool_call: ToolCallContext,
    capability_map: ProviderCapabilityMap,
    policy_decision: PolicyDecision,
) -> ToolExecutionMode:
    if policy_decision.decision != PolicyAction.ALLOW:
        return ToolExecutionMode.DETERMINISTIC

    # Deterministic mode enforced by policy is always honored.
    if policy_decision.enforced_mode == ToolExecutionMode.DETERMINISTIC:
        return ToolExecutionMode.DETERMINISTIC

    # Safety fallback: state-changing or high-impact calls never run provider-native.
    # This applies even if policy accidentally enforces provider_native.
    if tool_call.is_state_changing or tool_call.risk_tier in {RiskTier.HIGH, RiskTier.CRITICAL}:
        return ToolExecutionMode.DETERMINISTIC

    # Capability uncertainty also forces deterministic mode.
    if capability_map.should_force_deterministic():
        return ToolExecutionMode.DETERMINISTIC

    if policy_decision.enforced_mode is not None:
        return policy_decision.enforced_mode

    if tool_call.requested_mode == ToolExecutionMode.DETERMINISTIC:
        return ToolExecutionMode.DETERMINISTIC

    return ToolExecutionMode.PROVIDER_NATIVE
