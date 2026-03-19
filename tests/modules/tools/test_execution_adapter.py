"""
File: test_execution_adapter.py
Path: tests/modules/tools/test_execution_adapter.py
Role: Unit tests for default ToolExecutionAdapter contract helpers.
Used By:
 - pytest
Depends On:
 - src/tools/execution_adapter.py
 - src/schemas/tool_io.py
 - src/tools/registry.py
Notes:
 - Covers default optional hooks and concrete implementation surface.
"""

from __future__ import annotations

from src.schemas.tool_io import ToolCallContext, ToolResult, ToolStatus
from src.tools.execution_adapter import ToolExecutionAdapter
from src.tools.registry import ToolDescriptor


class _AdapterDouble(ToolExecutionAdapter):
    @property
    def backend_id(self) -> str:
        return "adapter-double"

    def execute(self, call: ToolCallContext, descriptor: ToolDescriptor) -> ToolResult:
        _ = (call, descriptor)
        return ToolResult(
            schema_version="1.0",
            call_id="tc_adapter",
            tool_name="test_tool",
            status=ToolStatus.SUCCESS,
            result={"value": {"ok": True}},
        )


def _call() -> ToolCallContext:
    return ToolCallContext(
        schema_version="1.0",
        call_id="tc_1",
        session_id="sess_1",
        run_id="run_1",
        job_id="job_1",
        task_id="task_1",
        agent_id="agent_1",
        provider_id="openai",
        tool_name="test_tool",
        arguments={},
    )


def test_adapter_contract_execute_and_backend_id() -> None:
    adapter = _AdapterDouble()
    descriptor = ToolDescriptor(name="test_tool", handler=lambda: {"ok": True})
    result = adapter.execute(_call(), descriptor)
    assert adapter.backend_id == "adapter-double"
    assert result.status == ToolStatus.SUCCESS
    assert result.result == {"value": {"ok": True}}


def test_adapter_contract_optional_hooks_default_values() -> None:
    adapter = _AdapterDouble()
    assert adapter.request_cancellation("tc_cancel") is False
    assert adapter.control_stats() == {}
    assert adapter.cleanup_events(limit=5) == []
    assert adapter.drain_progress_events("tc_progress") == []
