"""
File: tool_wiring.py
Path: packages/exo-adapter-openai/src/exo_adapter_openai/tool_wiring.py
Role: Provider package tool-wrapper wiring for OpenAI FunctionTool integration.
Used By:
 - provider package consumers
Depends On:
 - exo_brain_core_contracts.tool_io
 - openai-agents FunctionTool
Notes:
 - Avoids direct dependency on monorepo registry/executor implementations.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Iterable, Protocol

from agents import FunctionTool  # type: ignore[import-not-found,import-untyped]

from exo_brain_core_contracts import RiskTier, ToolCallContext, ToolStatus


class ToolDescriptorProtocol(Protocol):
    name: str
    description: str
    parameters_schema: dict[str, Any] | None
    risk_tier: Any
    is_state_changing: bool


class ToolRegistryProtocol(Protocol):
    def list_descriptors(self) -> Iterable[ToolDescriptorProtocol]:
        ...


class ToolExecutorProtocol(Protocol):
    def execute(self, call: ToolCallContext) -> Any:
        ...


def _coerce_risk_tier(value: Any) -> RiskTier:
    if isinstance(value, RiskTier):
        return value
    candidate = str(getattr(value, "value", value)).strip().lower()
    for tier in RiskTier:
        if tier.value == candidate:
            return tier
    return RiskTier.LOW


def _is_success_status(status: Any) -> bool:
    if isinstance(status, ToolStatus):
        return status == ToolStatus.SUCCESS
    candidate = str(getattr(status, "value", status)).strip().lower()
    return candidate == ToolStatus.SUCCESS.value


def _render_tool_error(error: Any) -> str:
    if error is None:
        return "unknown error"
    raw_message = getattr(error, "message", None)
    if raw_message not in (None, ""):
        message = str(raw_message).strip()
        if message:
            return message
    code = str(getattr(error, "code", "")).strip()
    if code:
        return code
    return str(error)


def build_agent_tools(
    tool_registry: ToolRegistryProtocol,
    tool_executor: ToolExecutorProtocol,
    session_id: str = "",
    agent_id: str = "exo-agent",
    provider_id: str = "openai",
    tenant_id: str = "default",
) -> list[FunctionTool]:
    """Build fresh FunctionTool wrappers for all currently registered descriptors."""
    tools: list[FunctionTool] = []
    for descriptor in tool_registry.list_descriptors():
        tools.append(_make_function_tool(descriptor, tool_executor, session_id, agent_id, provider_id, tenant_id))
    return tools


def _make_function_tool(
    desc: ToolDescriptorProtocol,
    tool_executor: ToolExecutorProtocol,
    session_id: str,
    agent_id: str,
    provider_id: str,
    tenant_id: str,
) -> FunctionTool:
    async def _execute(ctx: Any, args_str: str) -> str:
        del ctx
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
            tool_name=str(desc.name),
            arguments=kwargs,
            tenant_id=tenant_id,
            identity_tenant_id=tenant_id,
            risk_tier=_coerce_risk_tier(getattr(desc, "risk_tier", RiskTier.LOW)),
            is_state_changing=bool(getattr(desc, "is_state_changing", False)),
        )
        result = tool_executor.execute(call)
        if _is_success_status(getattr(result, "status", "")):
            payload = getattr(result, "result", None) or {}
            value = payload.get("value", payload) if isinstance(payload, dict) else payload
            if isinstance(value, dict):
                return json.dumps(value)
            return "" if value is None else str(value)
        return f"TOOL_EXECUTION_ERROR: {_render_tool_error(getattr(result, 'error', None))}"

    params_schema = getattr(desc, "parameters_schema", None) or {"type": "object", "properties": {}, "required": []}

    return FunctionTool(
        name=str(desc.name),
        description=(getattr(desc, "description", "") or str(desc.name)),
        params_json_schema=params_schema,
        on_invoke_tool=_execute,
        strict_json_schema=False,
    )


__all__ = ["build_agent_tools"]
