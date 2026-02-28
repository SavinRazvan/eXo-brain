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


@dataclass(slots=True)
class McpServerRecord:
    server_id: str
    endpoint: str
    trust_tier: McpTrustTier
    enabled: bool = True
    timeout_ms: int = 30000
    metadata: dict[str, Any] = field(default_factory=dict)


class McpRegistry:
    def __init__(self) -> None:
        self._servers: dict[str, McpServerRecord] = {}

    def register_server(self, record: McpServerRecord) -> None:
        self._servers[record.server_id] = record

    def get_server(self, server_id: str) -> McpServerRecord:
        record = self._servers.get(server_id)
        if record is None:
            raise KeyError(f"MCP server '{server_id}' is not registered")
        if not record.enabled:
            raise ValueError(f"MCP server '{server_id}' is disabled")
        return record

    def list_servers(self) -> list[str]:
        return sorted(self._servers.keys())
