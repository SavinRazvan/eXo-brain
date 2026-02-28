"""
File: test_mcp_tool_adapter.py
Path: tests/integration/test_mcp_tool_adapter.py
Role: Integration tests for MCP tool adapter trust-tier and policy behavior.
Used By:
 - pytest
Depends On:
 - src/mcp/mcp_registry.py
 - src/mcp/mcp_client_adapter.py
 - src/mcp/mcp_tool_adapter.py
 - src/policies/middleware.py
 - src/schemas/tool_io.py
Notes:
 - Uses local callable MCP client to keep tests deterministic.
"""

from __future__ import annotations

import asyncio

from src.mcp.mcp_client_adapter import LocalCallableMcpClientAdapter
from src.mcp.mcp_registry import McpRegistry, McpServerRecord, McpTrustTier
from src.mcp.mcp_tool_adapter import McpToolAdapter
from src.policies.middleware import DeterministicFirstPolicyMiddleware
from src.schemas.tool_io import RiskTier, ToolCallContext, ToolStatus


def _context(is_state_changing: bool = False, risk_tier: RiskTier = RiskTier.LOW) -> ToolCallContext:
    return ToolCallContext(
        schema_version="1.0",
        call_id="tc_mcp",
        session_id="sess_1",
        run_id="run_1",
        job_id="job_1",
        task_id="task_1",
        agent_id="agent_1",
        provider_id="openai",
        tool_name="lookup",
        arguments={"value": 3},
        is_state_changing=is_state_changing,
        risk_tier=risk_tier,
    )


def test_mcp_adapter_executes_tool_on_trusted_server() -> None:
    registry = McpRegistry()
    registry.register_server(
        McpServerRecord(
            server_id="trusted_server",
            endpoint="local://trusted",
            trust_tier=McpTrustTier.TRUSTED,
        )
    )
    client = LocalCallableMcpClientAdapter(
        tools={
            ("trusted_server", "lookup"): lambda args: {"result": args["value"] * 2},
        }
    )
    adapter = McpToolAdapter(registry=registry, client=client, policy=DeterministicFirstPolicyMiddleware())
    result = asyncio.run(adapter.execute("trusted_server", "lookup", _context()))
    assert result.status == ToolStatus.SUCCESS
    assert result.result == {"value": {"result": 6}}


def test_mcp_adapter_blocks_state_change_on_restricted_server() -> None:
    registry = McpRegistry()
    registry.register_server(
        McpServerRecord(
            server_id="restricted_server",
            endpoint="local://restricted",
            trust_tier=McpTrustTier.RESTRICTED,
        )
    )
    client = LocalCallableMcpClientAdapter(
        tools={
            ("restricted_server", "lookup"): lambda args: {"result": args["value"]},
        }
    )
    adapter = McpToolAdapter(registry=registry, client=client, policy=DeterministicFirstPolicyMiddleware())
    result = asyncio.run(adapter.execute("restricted_server", "lookup", _context(is_state_changing=True)))
    assert result.status == ToolStatus.ERROR
    assert result.error.code == "MCP_VALIDATION_ERROR"
