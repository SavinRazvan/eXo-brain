"""
File: test_mcp_tool_adapter.py
Path: tests/modules/mcp/test_mcp_tool_adapter.py
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
from src.mcp.mcp_registry import McpHealthState, McpRegistry, McpServerRecord, McpTrustTier
from src.mcp.mcp_tool_adapter import McpToolAdapter
from src.observability.logging import StructuredLogger
from src.policies.middleware import DeterministicFirstPolicyMiddleware
from src.resilience.compensation_hooks import CompensationHooks
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
    assert result.result is not None
    assert result.result["value"] == {"result": 6}


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


def test_mcp_adapter_blocks_unavailable_server_from_healthcheck() -> None:
    class UnavailableMcpClient(LocalCallableMcpClientAdapter):
        async def healthcheck(self, server_id: str) -> dict[str, str]:
            return {"state": "unavailable", "reason": "maintenance"}

    registry = McpRegistry()
    registry.register_server(
        McpServerRecord(
            server_id="degraded_server",
            endpoint="local://degraded",
            trust_tier=McpTrustTier.TRUSTED,
        )
    )
    client = UnavailableMcpClient(
        tools={
            ("degraded_server", "lookup"): lambda args: {"result": args["value"]},
        }
    )
    adapter = McpToolAdapter(registry=registry, client=client, policy=DeterministicFirstPolicyMiddleware())
    result = asyncio.run(adapter.execute("degraded_server", "lookup", _context()))
    assert result.status == ToolStatus.ERROR
    assert result.error.code == "MCP_VALIDATION_ERROR"
    assert "unavailable" in (result.error.message or "")
    assert registry.get_server_health("degraded_server").state == McpHealthState.UNAVAILABLE


def test_mcp_adapter_retries_timeout_and_succeeds_with_observability_logs() -> None:
    class TimeoutThenSuccessClient(LocalCallableMcpClientAdapter):
        def __init__(self) -> None:
            super().__init__(tools={("retry_server", "lookup"): lambda args: {"result": args["value"] + 1}})
            self._attempt = 0

        async def call_tool(self, server_id: str, tool_name: str, arguments: dict[str, object]) -> dict[str, object]:
            self._attempt += 1
            if self._attempt == 1:
                await asyncio.sleep(0.05)
            return {"result": int(arguments["value"]) + 1}

    registry = McpRegistry()
    registry.register_server(
        McpServerRecord(
            server_id="retry_server",
            endpoint="local://retry",
            trust_tier=McpTrustTier.TRUSTED,
            timeout_ms=10,
            metadata={"max_retries": 1},
        )
    )
    logger = StructuredLogger()
    adapter = McpToolAdapter(
        registry=registry,
        client=TimeoutThenSuccessClient(),
        policy=DeterministicFirstPolicyMiddleware(),
        logger=logger,
    )
    result = asyncio.run(adapter.execute("retry_server", "lookup", _context()))
    assert result.status == ToolStatus.SUCCESS
    assert result.execution.attempt == 2
    assert result.result is not None
    assert result.result["mcp_observability"]["attempt"] == 2
    events = {record.event for record in logger.records()}
    assert "mcp.call.timeout" in events
    assert "mcp.call.retry" in events
    assert "mcp.call.succeeded" in events


def test_mcp_adapter_returns_timeout_when_retries_exhausted() -> None:
    class AlwaysTimeoutClient(LocalCallableMcpClientAdapter):
        async def call_tool(self, server_id: str, tool_name: str, arguments: dict[str, object]) -> dict[str, object]:
            await asyncio.sleep(0.05)
            return {"result": 0}

    registry = McpRegistry()
    registry.register_server(
        McpServerRecord(
            server_id="timeout_server",
            endpoint="local://timeout",
            trust_tier=McpTrustTier.TRUSTED,
            timeout_ms=10,
            metadata={"max_retries": 1},
        )
    )
    adapter = McpToolAdapter(
        registry=registry,
        client=AlwaysTimeoutClient(tools={}),
        policy=DeterministicFirstPolicyMiddleware(),
    )
    result = asyncio.run(adapter.execute("timeout_server", "lookup", _context()))
    assert result.status == ToolStatus.TIMEOUT
    assert result.error.code == "MCP_TIMEOUT"
    assert result.execution.attempt == 2


def test_mcp_adapter_runs_compensation_hook_for_timeout() -> None:
    class AlwaysTimeoutClient(LocalCallableMcpClientAdapter):
        async def call_tool(self, server_id: str, tool_name: str, arguments: dict[str, object]) -> dict[str, object]:
            await asyncio.sleep(0.05)
            return {"result": 0}

    registry = McpRegistry()
    registry.register_server(
        McpServerRecord(
            server_id="timeout_server",
            endpoint="local://timeout",
            trust_tier=McpTrustTier.TRUSTED,
            timeout_ms=10,
            metadata={"max_retries": 0},
        )
    )
    observed: list[dict[str, object]] = []
    hooks = CompensationHooks()
    hooks.register("MCP_TIMEOUT", lambda payload: observed.append(dict(payload)))
    adapter = McpToolAdapter(
        registry=registry,
        client=AlwaysTimeoutClient(tools={}),
        policy=DeterministicFirstPolicyMiddleware(),
        compensation_hooks=hooks,
    )
    result = asyncio.run(adapter.execute("timeout_server", "lookup", _context()))

    assert result.status == ToolStatus.TIMEOUT
    assert len(observed) == 1
    assert observed[0]["tool_name"] == "lookup"
    assert observed[0]["server_id"] == "timeout_server"


def test_mcp_adapter_logs_compensation_hook_failures() -> None:
    class FailingClient(LocalCallableMcpClientAdapter):
        async def call_tool(self, server_id: str, tool_name: str, arguments: dict[str, object]) -> dict[str, object]:
            raise RuntimeError("simulated failure")

    registry = McpRegistry()
    registry.register_server(
        McpServerRecord(
            server_id="failing_server",
            endpoint="local://failing",
            trust_tier=McpTrustTier.TRUSTED,
            timeout_ms=50,
        )
    )
    hooks = CompensationHooks()

    def _broken_hook(payload: dict) -> None:
        raise RuntimeError(f"hook-failure:{payload.get('tool_name')}")

    hooks.register("MCP_EXECUTION_ERROR", _broken_hook)
    logger = StructuredLogger()
    adapter = McpToolAdapter(
        registry=registry,
        client=FailingClient(tools={}),
        policy=DeterministicFirstPolicyMiddleware(),
        compensation_hooks=hooks,
        logger=logger,
    )
    result = asyncio.run(adapter.execute("failing_server", "lookup", _context()))

    assert result.status == ToolStatus.ERROR
    events = {record.event for record in logger.records()}
    assert "mcp.compensation_hook.failed" in events
