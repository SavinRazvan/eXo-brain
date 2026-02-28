"""
File: mcp_client_adapter.py
Path: src/mcp/mcp_client_adapter.py
Role: MCP client adapter contract and local callable-backed implementation.
Used By:
 - src/mcp/mcp_tool_adapter.py
Depends On:
 - abc
Notes:
 - Real network MCP clients can implement this interface without changing core logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable


class McpClientAdapter(ABC):
    @abstractmethod
    async def call_tool(self, server_id: str, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute one MCP tool call and return normalized JSON-like output."""

    @abstractmethod
    async def healthcheck(self, server_id: str) -> dict[str, Any]:
        """Return health metadata for one MCP server."""


class LocalCallableMcpClientAdapter(McpClientAdapter):
    def __init__(self, tools: dict[tuple[str, str], Callable[[dict[str, Any]], dict[str, Any]]]) -> None:
        self._tools = tools

    async def call_tool(self, server_id: str, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        key = (server_id, tool_name)
        handler = self._tools.get(key)
        if handler is None:
            raise KeyError(f"MCP tool '{tool_name}' not registered for server '{server_id}'")
        return handler(arguments)

    async def healthcheck(self, server_id: str) -> dict[str, Any]:
        return {"state": "healthy", "server_id": server_id}
