"""
File: mcp_registry.py
Path: src/mcp/mcp_registry.py
Role: MCP server registry with trust-tier metadata and enablement controls.
Used By:
 - src/mcp/mcp_tool_adapter.py
Depends On:
 - dataclasses
Notes:
 - Registry controls which MCP servers/tools are available at runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class McpTrustTier(str, Enum):
    TRUSTED = "trusted"
    RESTRICTED = "restricted"
    SANDBOXED = "sandboxed"


class McpHealthState(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


@dataclass(slots=True)
class McpServerRecord:
    server_id: str
    endpoint: str
    trust_tier: McpTrustTier
    enabled: bool = True
    timeout_ms: int = 30000
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class McpServerHealth:
    state: McpHealthState = McpHealthState.HEALTHY
    reason: str = ""


class McpRegistry:
    def __init__(self) -> None:
        self._servers: dict[str, McpServerRecord] = {}
        self._health: dict[str, McpServerHealth] = {}

    def register_server(self, record: McpServerRecord) -> None:
        self._servers[record.server_id] = record
        self._health.setdefault(record.server_id, McpServerHealth())

    def get_server(self, server_id: str) -> McpServerRecord:
        record = self._servers.get(server_id)
        if record is None:
            raise KeyError(f"MCP server '{server_id}' is not registered")
        if not record.enabled:
            raise ValueError(f"MCP server '{server_id}' is disabled")
        health = self._health.get(server_id, McpServerHealth())
        if health.state == McpHealthState.UNAVAILABLE:
            reason = f": {health.reason}" if health.reason else ""
            raise ValueError(f"MCP server '{server_id}' is unavailable{reason}")
        return record

    def list_servers(self) -> list[str]:
        return sorted(self._servers.keys())

    def set_server_health(
        self,
        server_id: str,
        state: McpHealthState,
        reason: str = "",
    ) -> None:
        if server_id not in self._servers:
            raise KeyError(f"MCP server '{server_id}' is not registered")
        self._health[server_id] = McpServerHealth(state=state, reason=reason)

    def get_server_health(self, server_id: str) -> McpServerHealth:
        if server_id not in self._servers:
            raise KeyError(f"MCP server '{server_id}' is not registered")
        return self._health.get(server_id, McpServerHealth())

    def list_server_health(self) -> dict[str, McpServerHealth]:
        return {server_id: self._health.get(server_id, McpServerHealth()) for server_id in sorted(self._servers.keys())}
