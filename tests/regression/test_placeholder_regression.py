"""
File: test_placeholder_regression.py
Path: tests/regression/test_placeholder_regression.py
Role: Regression tests for policy/tool envelope compatibility.
Used By:
 - pytest
Depends On:
 - src/schemas/tool_io.py
Notes:
 - Confirms blocked result envelope remains stable for callers.
"""

from src.schemas.tool_io import ToolCallContext, blocked_result


def test_blocked_result_envelope_regression() -> None:
    context = ToolCallContext(
        schema_version="1.0",
        call_id="tc_regression",
        session_id="sess_1",
        run_id="run_1",
        job_id="job_1",
        task_id="task_1",
        agent_id="agent_1",
        provider_id="openai",
        tool_name="dangerous_tool",
        arguments={},
    )
    result = blocked_result(context, reason_code="BLOCKED_TEST", message="blocked")
    assert result.error.details == {"reason_code": "BLOCKED_TEST"}
