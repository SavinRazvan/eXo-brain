"""
File: test_mcp_registry.py
Path: tests/unit/test_mcp_registry.py
Role: Unit tests for MCP registry server health and availability controls.
Used By:
 - pytest
Depends On:
 - src/mcp/mcp_registry.py
Notes:
 - Verifies per-server health state influences MCP availability checks.
"""

from src.mcp.mcp_registry import McpHealthState, McpRegistry, McpServerRecord, McpTrustTier


def test_registry_tracks_server_health_state() -> None:
    registry = McpRegistry()
    registry.register_server(
        McpServerRecord(
            server_id="mcp_health",
            endpoint="local://mcp-health",
            trust_tier=McpTrustTier.TRUSTED,
        )
    )
    assert registry.get_server_health("mcp_health").state == McpHealthState.HEALTHY
    registry.set_server_health("mcp_health", McpHealthState.DEGRADED, reason="latency spike")
    health = registry.get_server_health("mcp_health")
    assert health.state == McpHealthState.DEGRADED
    assert health.reason == "latency spike"


def test_registry_blocks_unavailable_server_access() -> None:
    registry = McpRegistry()
    registry.register_server(
        McpServerRecord(
            server_id="mcp_unavailable",
            endpoint="local://mcp-unavailable",
            trust_tier=McpTrustTier.TRUSTED,
        )
    )
    registry.set_server_health("mcp_unavailable", McpHealthState.UNAVAILABLE, reason="outage")
    try:
        registry.get_server("mcp_unavailable")
    except ValueError as exc:
        assert "unavailable" in str(exc)
        assert "outage" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("Expected unavailable server lookup to fail")
