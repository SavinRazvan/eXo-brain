"""
File: test_tool_wiring.py
Path: tests/modules/runtime/test_tool_wiring.py
Role: Unit tests for runtime tool wiring function wrappers.
Used By:
 - pytest
Depends On:
 - exo_adapter_openai.tool_wiring (via src/runtime/tool_wiring.py re-export)
 - src/tools/registry.py
 - src/schemas/tool_io.py
Notes:
 - Validates success/error/input parsing paths for packaged OpenAI tool wiring.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.metadata import version

import pytest

from src.runtime.tool_wiring import build_agent_tools
from src.schemas.tool_io import NormalizedError, ToolResult, ToolStatus
from src.tools.registry import ToolDescriptor, ToolRegistry


@dataclass
class _ExecutorDouble:
    result: ToolResult

    def __post_init__(self) -> None:
        self.calls = []

    def execute(self, call):
        self.calls.append(call)
        return self.result


def _make_result(*, status: ToolStatus, result: dict | None = None, error: NormalizedError | None = None) -> ToolResult:
    return ToolResult(
        schema_version="1.0",
        call_id="tc_test",
        tool_name="add",
        status=status,
        result=result,
        error=error or NormalizedError(),
    )


def _single_tool(executor: _ExecutorDouble):
    registry = ToolRegistry()
    registry.register(
        ToolDescriptor(
            name="add",
            handler=lambda a, b: a + b,
            description="Adds two numbers.",
            parameters_schema={"type": "object"},
        )
    )
    tools = build_agent_tools(
        registry,
        executor,  # type: ignore[arg-type]
        session_id="sess_abc",
        agent_id="agent_math",
        provider_id="openai-test",
        tenant_id="tenant_x",
    )
    assert len(tools) == 1
    return tools[0]


@pytest.mark.asyncio
async def test_tool_wrapper_returns_input_error_on_invalid_json() -> None:
    executor = _ExecutorDouble(result=_make_result(status=ToolStatus.SUCCESS, result={"value": {"ok": True}}))
    tool = _single_tool(executor)
    payload = await tool.on_invoke_tool(None, "{bad json")
    assert payload.startswith("TOOL_INPUT_ERROR:")
    assert executor.calls == []


@pytest.mark.asyncio
async def test_tool_wrapper_executes_and_serializes_dict_value() -> None:
    executor = _ExecutorDouble(result=_make_result(status=ToolStatus.SUCCESS, result={"value": {"sum": 3}}))
    tool = _single_tool(executor)
    payload = await tool.on_invoke_tool(None, json.dumps({"a": 1, "b": 2}))
    assert json.loads(payload) == {"sum": 3}
    assert len(executor.calls) == 1
    call = executor.calls[0]
    assert call.session_id == "sess_abc"
    assert call.agent_id == "agent_math"
    assert call.provider_id == "openai-test"
    assert call.tenant_id == "tenant_x"
    assert call.tool_name == "add"
    assert call.arguments == {"a": 1, "b": 2}


@pytest.mark.asyncio
async def test_tool_wrapper_serializes_non_dict_value_as_string() -> None:
    executor = _ExecutorDouble(result=_make_result(status=ToolStatus.SUCCESS, result={"value": 7}))
    tool = _single_tool(executor)
    payload = await tool.on_invoke_tool(None, json.dumps({"a": 1, "b": 6}))
    assert payload == "7"


@pytest.mark.asyncio
async def test_tool_wrapper_uses_payload_as_value_when_value_key_missing() -> None:
    executor = _ExecutorDouble(result=_make_result(status=ToolStatus.SUCCESS, result={"sum": 11}))
    tool = _single_tool(executor)
    payload = await tool.on_invoke_tool(None, json.dumps({"a": 5, "b": 6}))
    assert json.loads(payload) == {"sum": 11}


@pytest.mark.asyncio
async def test_tool_wrapper_returns_execution_error_message_precedence() -> None:
    executor = _ExecutorDouble(
        result=_make_result(
            status=ToolStatus.ERROR,
            error=NormalizedError(code="ERR_CODE", message="bad args"),
        )
    )
    tool = _single_tool(executor)
    payload = await tool.on_invoke_tool(None, json.dumps({"a": 1}))
    assert payload == "TOOL_EXECUTION_ERROR: bad args"


@pytest.mark.asyncio
async def test_tool_wrapper_returns_execution_error_fallbacks() -> None:
    executor = _ExecutorDouble(
        result=_make_result(
            status=ToolStatus.ERROR,
            error=NormalizedError(code="ERR_ONLY_CODE", message=None),
        )
    )
    tool = _single_tool(executor)
    payload = await tool.on_invoke_tool(None, "")
    # exo-adapter-openai 0.1.1 renders str(None); 0.1.2+ falls back to error.code
    openai_adapter_version = version("exo-adapter-openai")
    if openai_adapter_version >= "0.1.2":
        assert payload == "TOOL_EXECUTION_ERROR: ERR_ONLY_CODE"
    else:
        assert payload == "TOOL_EXECUTION_ERROR: None"
