"""
File: tool_wiring.py
Path: src/runtime/tool_wiring.py
Role: Dynamic tool-to-adapter wiring — builds FunctionTool wrappers from ToolRegistry descriptors.
Used By:
 - src/runtime/openai_agents_runtime.py
Depends On:
 - src/tools/registry.py
 - src/tools/executor.py
 - src/schemas/tool_io.py
Notes:
 - Called on every run_turn to pick up any tools registered after start_session (late binding).
 - Sync executor.execute() is called inside an async body — valid, runs in same event loop thread.
 - This file is the ONLY file outside src/tools/ that imports FunctionTool; never imported by core.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from agents import FunctionTool

from src.schemas.tool_io import ToolCallContext, ToolStatus
from src.tools.executor import DeterministicToolExecutor
from src.tools.registry import ToolDescriptor, ToolRegistry


def build_agent_tools(
    tool_registry: ToolRegistry,
    tool_executor: DeterministicToolExecutor,
    session_id: str = "",
    agent_id: str = "exo-agent",
    provider_id: str = "openai",
    tenant_id: str = "default",
) -> list[FunctionTool]:
    """Return a fresh list of FunctionTool wrappers for every descriptor in the registry.

    Rebuilding on every run_turn ensures tools registered after start_session are visible.
    """
    tools: list[FunctionTool] = []
    for descriptor in tool_registry.list_descriptors():
        tools.append(_make_function_tool(descriptor, tool_executor, session_id, agent_id, provider_id, tenant_id))
    return tools


def _make_function_tool(
    desc: ToolDescriptor,
    tool_executor: DeterministicToolExecutor,
    session_id: str,
    agent_id: str,
    provider_id: str,
    tenant_id: str,
) -> FunctionTool:
    """Build a single FunctionTool that routes through DeterministicToolExecutor."""

    async def _execute(ctx: Any, args_str: str) -> str:
        call_id = f"tc_{uuid.uuid4().hex[:12]}"
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        try:
            kwargs: dict[str, Any] = json.loads(args_str) if args_str else {}
        except json.JSONDecodeError as exc:
            return f"TOOL_INPUT_ERROR: {exc}"

        call = ToolCallContext(
            schema_version="1.0",
            call_id=call_id,
            session_id=session_id or "session_unknown",
            run_id=run_id,
            job_id="job_api",
            task_id="task_api",
            agent_id=agent_id,
            provider_id=provider_id,
            tool_name=desc.name,
            arguments=kwargs,
            tenant_id=tenant_id,
            risk_tier=desc.risk_tier,
            is_state_changing=desc.is_state_changing,
        )
        result = tool_executor.execute(call)
        if result.status == ToolStatus.SUCCESS:
            payload = result.result or {}
            value = payload.get("value", payload)
            return json.dumps(value) if isinstance(value, dict) else str(value)
        err = result.error
        return f"TOOL_EXECUTION_ERROR: {err.message or err.code or 'unknown error'}"

    params_schema = desc.parameters_schema or {"type": "object", "properties": {}, "required": []}

    return FunctionTool(
        name=desc.name,
        description=desc.description or desc.name,
        params_json_schema=params_schema,
        on_invoke_tool=_execute,
        strict_json_schema=False,
    )
