"""
File: test_schemas.py
Path: tests/modules/schemas/test_schemas.py
Role: Unit tests for schema envelopes in tool_io and events modules.
Used By:
 - pytest
Depends On:
 - src/schemas/tool_io.py
 - src/schemas/events.py
Notes:
 - Keeps contract shapes stable for downstream runtime and policy modules.
"""

from src.schemas.events import RuntimeEventType
from src.schemas.tool_io import RiskTier, ToolCallContext, ToolStatus, blocked_result


def test_blocked_result_envelope_contains_policy_code() -> None:
    call = ToolCallContext(
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
        risk_tier=RiskTier.HIGH,
        is_state_changing=True,
    )

    result = blocked_result(call, reason_code="POLICY_BLOCK", message="blocked")
    assert result.status == ToolStatus.BLOCKED
    assert result.error.code == "POLICY_BLOCKED"
    assert result.audit is not None
    assert result.audit.decision_reason_code == "POLICY_BLOCK"


def test_runtime_event_type_values_are_stable() -> None:
    assert RuntimeEventType.TOOL_INTENT.value == "tool_intent"
    assert RuntimeEventType.OUTPUT_DELTA.value == "output_delta"
    assert RuntimeEventType.RUN_COMPLETE.value == "run_complete"
