"""
File: network_mcp_client_adapter.py
Path: src/mcp/network_mcp_client_adapter.py
Role: Network-capable MCP client adapter using injectable async transport.
Used By:
 - future runtime/bootstrap wiring
Depends On:
 - src/mcp/mcp_client_adapter.py
Notes:
 - Transport injection keeps adapter testable and provider-neutral.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from src.mcp.mcp_client_adapter import McpClientAdapter


TransportCallable = Callable[[str, str, dict[str, Any]], Awaitable[dict[str, Any]]]
HealthCallable = Callable[[str], Awaitable[dict[str, Any]]]


class NetworkMcpClientAdapter(McpClientAdapter):
    def __init__(self, call_transport: TransportCallable, health_transport: HealthCallable) -> None:
        self._call_transport = call_transport
        self._health_transport = health_transport

    async def call_tool(self, server_id: str, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return await self._call_transport(server_id, tool_name, dict(arguments))

    async def healthcheck(self, server_id: str) -> dict[str, Any]:
        return await self._health_transport(server_id)

