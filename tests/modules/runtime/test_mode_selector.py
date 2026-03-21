"""
File: test_mode_selector.py
Path: tests/modules/runtime/test_mode_selector.py
Role: Unit tests for deterministic-first runtime mode selection.
Used By:
 - pytest
Depends On:
 - src/runtime/mode_selector.py
 - src/runtime/capability_map.py
 - src/schemas/tool_io.py
Notes:
 - Verifies policy and capability rules route state-changing/high-impact calls safely.
"""

from src.runtime.capability_map import ProviderCapabilityMap
from src.runtime.mode_selector import select_execution_mode
from src.schemas.tool_io import (
    PolicyAction,
    PolicyDecision,
    RiskTier,
    ToolCallContext,
    ToolExecutionMode,
)


def _call_context(risk_tier: RiskTier = RiskTier.LOW, is_state_changing: bool = False) -> ToolCallContext:
    return ToolCallContext(
        schema_version="1.0",
        call_id="tc_1",
        session_id="sess_1",
        run_id="run_1",
        job_id="job_1",
        task_id="task_1",
        agent_id="agent_1",
        provider_id="openai",
        tool_name="demo_tool",
        arguments={},
        risk_tier=risk_tier,
        is_state_changing=is_state_changing,
    )


def _allow_decision(enforced: ToolExecutionMode | None = None) -> PolicyDecision:
    return PolicyDecision(
        schema_version="1.0",
        decision=PolicyAction.ALLOW,
        reason_code="ALLOW",
        message="allowed",
        enforced_mode=enforced,
    )


def test_high_risk_forces_deterministic() -> None:
    capability = ProviderCapabilityMap(provider_id="openai", reliability_score=5)
    mode = select_execution_mode(_call_context(risk_tier=RiskTier.HIGH), capability, _allow_decision())
    assert mode == ToolExecutionMode.DETERMINISTIC


def test_allow_and_strong_capabilities_use_provider_native() -> None:
    capability = ProviderCapabilityMap(
        provider_id="openai",
        supports_function_calling=True,
        supports_structured_output=True,
        reliability_score=5,
    )
    mode = select_execution_mode(_call_context(), capability, _allow_decision())
    assert mode == ToolExecutionMode.PROVIDER_NATIVE


def test_enforced_mode_overrides_default() -> None:
    capability = ProviderCapabilityMap(provider_id="openai", reliability_score=5)
    mode = select_execution_mode(
        _call_context(),
        capability,
        _allow_decision(enforced=ToolExecutionMode.DETERMINISTIC),
    )
    assert mode == ToolExecutionMode.DETERMINISTIC


def test_enforced_provider_native_falls_back_for_high_risk() -> None:
    capability = ProviderCapabilityMap(provider_id="openai", reliability_score=5)
    mode = select_execution_mode(
        _call_context(risk_tier=RiskTier.CRITICAL, is_state_changing=True),
        capability,
        _allow_decision(enforced=ToolExecutionMode.PROVIDER_NATIVE),
    )
    assert mode == ToolExecutionMode.DETERMINISTIC


def test_capability_gap_falls_back_to_deterministic() -> None:
    capability = ProviderCapabilityMap(
        provider_id="openai",
        supports_function_calling=False,
        supports_structured_output=True,
        reliability_score=5,
    )
    mode = select_execution_mode(_call_context(), capability, _allow_decision())
    assert mode == ToolExecutionMode.DETERMINISTIC


def test_non_allow_policy_forces_deterministic() -> None:
    capability = ProviderCapabilityMap(
        provider_id="openai",
        supports_function_calling=True,
        supports_structured_output=True,
        reliability_score=5,
    )
    deny = PolicyDecision(
        schema_version="1.0",
        decision=PolicyAction.DENY,
        reason_code="NO",
        message="no",
    )
    mode = select_execution_mode(_call_context(), capability, deny)
    assert mode == ToolExecutionMode.DETERMINISTIC


def test_enforced_provider_native_used_when_safe() -> None:
    capability = ProviderCapabilityMap(
        provider_id="openai",
        supports_function_calling=True,
        supports_structured_output=True,
        reliability_score=5,
    )
    mode = select_execution_mode(
        _call_context(),
        capability,
        _allow_decision(enforced=ToolExecutionMode.PROVIDER_NATIVE),
    )
    assert mode == ToolExecutionMode.PROVIDER_NATIVE


def test_requested_deterministic_honored_when_policy_enforced_none() -> None:
    capability = ProviderCapabilityMap(
        provider_id="openai",
        supports_function_calling=True,
        supports_structured_output=True,
        reliability_score=5,
    )
    call = _call_context()
    call = ToolCallContext(
        schema_version=call.schema_version,
        call_id=call.call_id,
        session_id=call.session_id,
        run_id=call.run_id,
        job_id=call.job_id,
        task_id=call.task_id,
        agent_id=call.agent_id,
        provider_id=call.provider_id,
        tool_name=call.tool_name,
        arguments=call.arguments,
        risk_tier=call.risk_tier,
        is_state_changing=call.is_state_changing,
        requested_mode=ToolExecutionMode.DETERMINISTIC,
    )
    mode = select_execution_mode(call, capability, _allow_decision())
    assert mode == ToolExecutionMode.DETERMINISTIC
